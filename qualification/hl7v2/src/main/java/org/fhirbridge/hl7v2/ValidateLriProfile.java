package org.fhirbridge.hl7v2;

import gov.cdc.InvalidFileException;
import gov.cdc.NistReport;
import gov.cdc.ProfileFetcher;
import gov.cdc.ProfileManager;
import gov.cdc.SummaryCount;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;

public final class ValidateLriProfile {
    private ValidateLriProfile() {
    }

    private static final class DirectoryProfileFetcher implements ProfileFetcher {
        private final Path root;
        private final String profileName;

        DirectoryProfileFetcher(Path root, String profileName) {
            this.root = root.toAbsolutePath().normalize();
            this.profileName = profileName;
        }

        private Path resolve(String requested) throws InvalidFileException {
            String normalized = requested.replace('\\', '/');
            while (normalized.startsWith("/")) {
                normalized = normalized.substring(1);
            }
            String prefix = profileName + "/";
            if (normalized.startsWith(prefix)) {
                normalized = normalized.substring(prefix.length());
            }
            Path resolved = root.resolve(normalized).normalize();
            if (!resolved.startsWith(root)) {
                throw new InvalidFileException("Profile path escaped bundle root");
            }
            if (!Files.isRegularFile(resolved)
                    && normalized.equals("VALUSETBINDINGS.xml")) {
                Path canonical = root.resolve("VALUESETBINDINGS.xml").normalize();
                if (canonical.startsWith(root) && Files.isRegularFile(canonical)) {
                    return canonical;
                }
            }
            return resolved;
        }

        @Override
        public String getFile(String file, boolean required)
                throws InvalidFileException {
            Path path = resolve(file);
            if (!Files.isRegularFile(path)) {
                if (required) {
                    throw new InvalidFileException(
                        "Required profile file is missing: " + path
                    );
                }
                return null;
            }
            try {
                return Files.readString(path);
            } catch (IOException exception) {
                throw new InvalidFileException(
                    "Unable to read profile file: " + path
                );
            }
        }

        @Override
        public InputStream getFileAsInputStream(String file, boolean required)
                throws InvalidFileException {
            Path path = resolve(file);
            if (!Files.isRegularFile(path)) {
                if (required) {
                    throw new InvalidFileException(
                        "Required profile file is missing: " + path
                    );
                }
                return null;
            }
            try {
                return Files.newInputStream(path);
            } catch (IOException exception) {
                throw new InvalidFileException(
                    "Unable to open profile file: " + path
                );
            }
        }
    }

    private static int total(SummaryCount count) {
        if (count == null) {
            return 0;
        }
        return count.getStructure() + count.getValueset() + count.getContent();
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 2 || args.length > 3) {
            System.err.println(
                "Usage: ValidateLriProfile PROFILE_DIRECTORY MESSAGE_ER7 [--report-only]"
            );
            System.exit(2);
        }
        boolean reportOnly = args.length == 3 && "--report-only".equals(args[2]);
        if (args.length == 3 && !reportOnly) {
            System.err.println("Unsupported third argument: " + args[2]);
            System.exit(2);
        }

        Path profileDirectory = Path.of(args[0]).toAbsolutePath().normalize();
        Path messagePath = Path.of(args[1]).toAbsolutePath().normalize();
        String message = Files.readString(messagePath);

        String profileName = "FHIRBRIDGE_LRI";
        ProfileManager manager = new ProfileManager(
            new DirectoryProfileFetcher(profileDirectory, profileName),
            profileName
        );
        NistReport report = manager.validate(message);

        SummaryCount errors = report.getErrorCounts();
        SummaryCount warnings = report.getWarningCounts();
        SummaryCount alerts = report.getAlertCounts();
        SummaryCount informational = report.getInformationalCounts();
        int errorTotal = total(errors);
        int warningTotal = total(warnings);
        int alertTotal = total(alerts);
        int informationalTotal = total(informational);

        // Preserve the entry-level evidence before the compact summary. The
        // Python qualification runner joins this report to the summary using
        // line-delimited JSON and can therefore assert expected error loci.
        System.out.println(NistReport.Companion.getNistGson().toJson(report));

        System.out.printf(
            "{\"status\":\"%s\","
                + "\"errors\":{\"structure\":%d,\"value_set\":%d,\"content\":%d},"
                + "\"warnings\":{\"structure\":%d,\"value_set\":%d,\"content\":%d},"
                + "\"alerts\":{\"structure\":%d,\"value_set\":%d,\"content\":%d},"
                + "\"informational\":{\"structure\":%d,\"value_set\":%d,\"content\":%d},"
                + "\"error_total\":%d,\"warning_total\":%d,"
                + "\"alert_total\":%d,\"informational_total\":%d}%n",
            report.getStatus(),
            errors == null ? 0 : errors.getStructure(),
            errors == null ? 0 : errors.getValueset(),
            errors == null ? 0 : errors.getContent(),
            warnings == null ? 0 : warnings.getStructure(),
            warnings == null ? 0 : warnings.getValueset(),
            warnings == null ? 0 : warnings.getContent(),
            alerts == null ? 0 : alerts.getStructure(),
            alerts == null ? 0 : alerts.getValueset(),
            alerts == null ? 0 : alerts.getContent(),
            informational == null ? 0 : informational.getStructure(),
            informational == null ? 0 : informational.getValueset(),
            informational == null ? 0 : informational.getContent(),
            errorTotal,
            warningTotal,
            alertTotal,
            informationalTotal
        );

        if (errorTotal != 0 && !reportOnly) {
            System.exit(1);
        }
    }
}
