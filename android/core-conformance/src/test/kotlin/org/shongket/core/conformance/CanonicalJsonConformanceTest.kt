package org.shongket.core.conformance

import java.io.File
import java.nio.charset.StandardCharsets
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class CanonicalJsonConformanceTest {
    @Test
    fun everyCommittedCanonicalVectorMatchesKotlinBytesAndHashes() {
        val cases = vectorDocuments().flatMap { (fileName, document) ->
            collectCanonicalCases(fileName, document)
        }

        require(cases.isNotEmpty()) { "no canonical vector cases were discovered" }
        cases.forEach { case ->
            val encoded = CanonicalJson.encode(case.value)
            val bytes = encoded.toByteArray(StandardCharsets.UTF_8)
            assertEquals(case.qualifiedName, case.canonicalText, encoded)
            case.byteLength?.let { assertEquals(case.qualifiedName, it, bytes.size.toLong()) }
            case.sha256?.let {
                assertEquals(case.qualifiedName, it, CanonicalJson.sha256Hex(bytes))
            }
        }

        writeLanguageReport(cases)
    }

    @Test
    fun identityVectorsExcludeOnlyDeclaredTransportFields() {
        val cases = vectorDocuments().flatMap { (fileName, document) ->
            collectIdentityCases(fileName, document)
        }

        require(cases.isNotEmpty()) { "no identity vector cases were discovered" }
        cases.forEach { case ->
            val filtered = case.payload.filterKeys { key -> key !in case.excludedFields }
            val canonical = CanonicalJson.encode(filtered)
            assertEquals(case.qualifiedName, case.canonicalText, canonical)
            assertEquals(case.qualifiedName, case.sha256, CanonicalJson.sha256Hex(filtered))
        }
    }

    @Test
    fun parserRefusesDuplicateKeysFloatsAndTrailingData() {
        assertThrows(IllegalArgumentException::class.java) {
            CanonicalJson.parse("""{"a":1,"a":2}""")
        }
        assertThrows(IllegalArgumentException::class.java) {
            CanonicalJson.parse("""{"a":1.5}""")
        }
        assertThrows(IllegalArgumentException::class.java) {
            CanonicalJson.parse("""{}[]""")
        }
    }

    @Test
    fun encoderRefusesFloatsAndNonStringKeys() {
        assertThrows(IllegalArgumentException::class.java) {
            CanonicalJson.encode(mapOf("value" to 1.5))
        }
        assertThrows(IllegalArgumentException::class.java) {
            CanonicalJson.encode(mapOf(1 to "value"))
        }
    }

    private fun vectorDocuments(): List<Pair<String, Any?>> =
        VECTOR_FILES.map { fileName ->
            val stream = requireNotNull(javaClass.classLoader?.getResourceAsStream(fileName)) {
                "missing conformance resource $fileName"
            }
            fileName to stream.bufferedReader(StandardCharsets.UTF_8).use { reader ->
                CanonicalJson.parse(reader.readText())
            }
        }

    private fun collectCanonicalCases(
        fileName: String,
        value: Any?,
        path: String = "$",
    ): List<CanonicalCase> {
        val result = mutableListOf<CanonicalCase>()
        when (value) {
            is Map<*, *> -> {
                val map = value.asStringMap()
                if ("value" in map && map["canonical_text"] is String) {
                    result += CanonicalCase(
                        qualifiedName = "$fileName:$path:${map["name"] ?: "unnamed"}",
                        value = map["value"],
                        canonicalText = map["canonical_text"] as String,
                        byteLength = map["byte_length"] as? Long,
                        sha256 = map["sha256"] as? String,
                    )
                }
                map.forEach { (key, child) ->
                    result += collectCanonicalCases(fileName, child, "$path.$key")
                }
            }
            is List<*> -> value.forEachIndexed { index, child ->
                result += collectCanonicalCases(fileName, child, "$path[$index]")
            }
        }
        return result
    }

    private fun collectIdentityCases(
        fileName: String,
        value: Any?,
        path: String = "$",
    ): List<IdentityCase> {
        val result = mutableListOf<IdentityCase>()
        when (value) {
            is Map<*, *> -> {
                val map = value.asStringMap()
                if (
                    map["payload"] is Map<*, *> &&
                    map["excluded_fields"] is List<*> &&
                    map["canonical_text"] is String &&
                    map["sha256"] is String
                ) {
                    result += IdentityCase(
                        qualifiedName = "$fileName:$path:${map["name"] ?: "unnamed"}",
                        payload = (map["payload"] as Map<*, *>).asStringMap(),
                        excludedFields = (map["excluded_fields"] as List<*>)
                            .map { it as String }
                            .toSet(),
                        canonicalText = map["canonical_text"] as String,
                        sha256 = map["sha256"] as String,
                    )
                }
                map.forEach { (key, child) ->
                    result += collectIdentityCases(fileName, child, "$path.$key")
                }
            }
            is List<*> -> value.forEachIndexed { index, child ->
                result += collectIdentityCases(fileName, child, "$path[$index]")
            }
        }
        return result
    }

    private fun writeLanguageReport(cases: List<CanonicalCase>) {
        val report = linkedMapOf<String, Any?>(
            "language" to "kotlin",
            "schema" to "shongket.conformance-report.v1.0",
            "vectors" to cases.sortedBy { it.qualifiedName }.map { case ->
                linkedMapOf(
                    "name" to case.qualifiedName,
                    "sha256" to CanonicalJson.sha256Hex(case.value),
                )
            },
        )
        val directory = File(requireNotNull(System.getProperty("shongket.report.dir")))
        check(directory.exists() || directory.mkdirs()) {
            "could not create conformance report directory"
        }
        File(directory, "kotlin-hashes.json").writeText(
            CanonicalJson.encode(report) + "\n",
            StandardCharsets.UTF_8,
        )
    }

    private fun Map<*, *>.asStringMap(): Map<String, Any?> =
        entries.associate { (key, value) ->
            (key as? String ?: error("non-string JSON key")) to value
        }

    private data class CanonicalCase(
        val qualifiedName: String,
        val value: Any?,
        val canonicalText: String,
        val byteLength: Long?,
        val sha256: String?,
    )

    private data class IdentityCase(
        val qualifiedName: String,
        val payload: Map<String, Any?>,
        val excludedFields: Set<String>,
        val canonicalText: String,
        val sha256: String,
    )

    private companion object {
        val VECTOR_FILES = listOf(
            "golden_vectors.json",
            "m1_conformance_vectors.json",
            "m2_process_vectors.json",
        )
    }
}
