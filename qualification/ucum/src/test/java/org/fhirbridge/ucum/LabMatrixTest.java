package org.fhirbridge.ucum;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

import java.io.FileInputStream;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import org.fhir.ucum.Decimal;
import org.fhir.ucum.UcumEssenceService;
import org.fhir.ucum.UcumException;
import org.fhir.ucum.UcumService;
import org.junit.jupiter.api.Test;
import org.yaml.snakeyaml.Yaml;

public class LabMatrixTest {

    @SuppressWarnings("unchecked")
    @Test
    void frozenLabConversionMatrixMatchesRealUcumProvider() throws Exception {
        String matrixPath = System.getProperty("ucumMatrix");
        String essencePath = System.getProperty("ucumEssence");
        assertNotNull(matrixPath, "ucumMatrix system property is required");
        assertNotNull(essencePath, "ucumEssence system property is required");

        Path matrix = Path.of(matrixPath);
        Path essence = Path.of(essencePath);
        if (!Files.isRegularFile(matrix) || !Files.isRegularFile(essence)) {
            throw new IllegalStateException("matrix and essence files must exist");
        }

        Map<String, Object> document;
        try (InputStream input = new FileInputStream(matrix.toFile())) {
            document = new Yaml().load(input);
        }

        List<Map<String, Object>> cases =
            (List<Map<String, Object>>) document.get("cases");
        assertNotNull(cases, "matrix must contain cases");

        UcumService service;
        try (InputStream input = new FileInputStream(essence.toFile())) {
            service = new UcumEssenceService(input);
        }

        for (Map<String, Object> item : cases) {
            String caseId = String.valueOf(item.get("case_id"));
            Map<String, Object> source =
                (Map<String, Object>) item.get("source");
            Map<String, Object> target =
                (Map<String, Object>) item.get("target");
            boolean expected =
                Boolean.TRUE.equals(item.get("expected_equivalent"));

            String sourceValue = String.valueOf(source.get("value"));
            String sourceUnit = String.valueOf(source.get("unit"));
            String targetValue = String.valueOf(target.get("value"));
            String targetUnit = String.valueOf(target.get("unit"));

            boolean observed = quantitiesEquivalent(
                service,
                sourceValue,
                sourceUnit,
                targetValue,
                targetUnit
            );

            assertEquals(
                expected,
                observed,
                () -> caseId
                    + " expected equivalence=" + expected
                    + " but observed=" + observed
                    + " for " + sourceValue + " " + sourceUnit
                    + " -> " + targetValue + " " + targetUnit
            );
        }
    }

    private static boolean quantitiesEquivalent(
        UcumService service,
        String sourceValue,
        String sourceUnit,
        String targetValue,
        String targetUnit
    ) {
        try {
            Decimal converted = service.convert(
                new Decimal(sourceValue),
                sourceUnit,
                targetUnit
            );
            return converted.comparesTo(new Decimal(targetValue)) == 0;
        } catch (UcumException exception) {
            return false;
        }
    }
}
