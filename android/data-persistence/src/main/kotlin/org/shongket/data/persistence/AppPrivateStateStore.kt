package org.shongket.data.persistence

import java.io.FileOutputStream
import java.io.IOException
import java.nio.ByteBuffer
import java.nio.channels.FileChannel
import java.nio.charset.CodingErrorAction
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption
import java.nio.file.StandardOpenOption
import org.shongket.core.conformance.CanonicalJson

class StatePersistenceException(message: String, cause: Throwable? = null) :
    IllegalStateException(message, cause)

class AppPrivateStateStore(
    rootDirectory: Path,
    private val maxDocumentBytes: Long = MAX_STATE_DOCUMENT_BYTES,
) {
    private val root = rootDirectory.toAbsolutePath().normalize()
    private val primary = safePath(PRIMARY_FILE)
    private val temporary = safePath("$PRIMARY_FILE.tmp")
    private val backup = safePath("$PRIMARY_FILE.last-good")
    private val backupTemporary = safePath("$PRIMARY_FILE.last-good.tmp")

    init {
        require(maxDocumentBytes in 1..MAX_STATE_DOCUMENT_BYTES) {
            "document limit is outside the supported range"
        }
    }

    @Synchronized
    fun save(snapshot: TransferSnapshot) {
        snapshot.validate()
        Files.createDirectories(root)
        val bytes = encodeDocument(snapshot)
        require(bytes.size.toLong() <= maxDocumentBytes) {
            "state document exceeds the configured limit"
        }

        writeAndSync(temporary, bytes)
        if (Files.isRegularFile(primary)) {
            Files.copy(
                primary,
                backupTemporary,
                StandardCopyOption.REPLACE_EXISTING,
                StandardCopyOption.COPY_ATTRIBUTES,
            )
            syncFile(backupTemporary)
            moveReplace(backupTemporary, backup)
        }
        moveReplace(temporary, primary)
        syncDirectoryBestEffort()
    }

    @Synchronized
    fun load(): LoadResult {
        Files.createDirectories(root)
        val events = mutableListOf<RecoveryEvent>()
        if (Files.exists(temporary)) {
            Files.deleteIfExists(temporary)
            events += RecoveryEvent.DISCARDED_TRUNCATED_TEMP
        }
        Files.deleteIfExists(backupTemporary)
        if (!Files.exists(primary)) return LoadResult(snapshot = null, events = events)

        return try {
            val decoded = decodeDocument(primary)
            LoadResult(
                snapshot = decoded.snapshot,
                events = events + decoded.events,
            )
        } catch (error: StatePersistenceException) {
            quarantinePrimary()
            events += RecoveryEvent.QUARANTINED_PRIMARY
            if (!Files.exists(backup)) {
                return LoadResult(
                    snapshot = null,
                    events = events,
                )
            }
            try {
                val decoded = decodeDocument(backup)
                LoadResult(
                    snapshot = decoded.snapshot,
                    events = events + RecoveryEvent.LOADED_LAST_GOOD + decoded.events,
                )
            } catch (_: StatePersistenceException) {
                LoadResult(
                    snapshot = null,
                    events = events + RecoveryEvent.LAST_GOOD_UNREADABLE,
                )
            }
        }
    }

    fun primaryPath(): Path = primary

    private fun encodeDocument(snapshot: TransferSnapshot): ByteArray {
        val state = snapshot.toJson()
        val unsigned = linkedMapOf<String, Any?>(
            "schema" to ENVELOPE_SCHEMA,
            "state" to state,
        )
        val document = LinkedHashMap(unsigned)
        document["document_checksum"] = CanonicalJson.sha256Hex(unsigned)
        return CanonicalJson.encodeToBytes(document)
    }

    private fun decodeDocument(path: Path): DecodedState {
        val size = try {
            Files.size(path)
        } catch (error: IOException) {
            throw StatePersistenceException("could not inspect state document", error)
        }
        if (size !in 1..maxDocumentBytes) {
            throw StatePersistenceException("state document is empty or oversized")
        }
        val bytes = try {
            Files.newInputStream(path).use { input ->
                input.readNBytes((maxDocumentBytes + 1).toInt())
            }
        } catch (error: IOException) {
            throw StatePersistenceException("could not read state document", error)
        }
        if (bytes.size.toLong() > maxDocumentBytes) {
            throw StatePersistenceException("state document exceeds its size limit")
        }
        val text = try {
            Charsets.UTF_8.newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT)
                .decode(ByteBuffer.wrap(bytes))
                .toString()
        } catch (error: Exception) {
            throw StatePersistenceException("state document is not valid UTF-8", error)
        }
        val rootValue = try {
            CanonicalJson.parse(
                text,
                maxDepth = 32,
                maxCharacters = maxDocumentBytes.toInt(),
            )
        } catch (error: IllegalArgumentException) {
            throw StatePersistenceException("state document is not valid JSON", error)
        }
        val document = rootValue.asStringMap("state envelope")
        if (CanonicalJson.encode(document) != text) {
            throw StatePersistenceException("state document is not canonical")
        }
        if (document.keys != ENVELOPE_KEYS) {
            throw StatePersistenceException("state envelope fields are invalid")
        }
        if (document["schema"] != ENVELOPE_SCHEMA) {
            throw StatePersistenceException("state envelope version is unsupported")
        }
        val checksum = document["document_checksum"] as? String
            ?: throw StatePersistenceException("state checksum is missing")
        val unsigned = linkedMapOf<String, Any?>(
            "schema" to document["schema"],
            "state" to document["state"],
        )
        if (CanonicalJson.sha256Hex(unsigned) != checksum) {
            throw StatePersistenceException("state checksum mismatch")
        }
        return decodeSnapshot(document["state"])
    }

    private fun decodeSnapshot(value: Any?): DecodedState {
        val state = value.asStringMap("transfer state")
        if (state.keys != STATE_KEYS) {
            throw StatePersistenceException("transfer state fields are invalid")
        }
        val expected = state.long("expected_fragments").toBoundedInt(
            "expected_fragments",
            1,
            MAX_EXPECTED_FRAGMENTS,
        )
        val fragmentValues = state["fragments"] as? List<*>
            ?: throw StatePersistenceException("fragments must be an array")
        if (fragmentValues.size > expected) {
            throw StatePersistenceException("fragment array exceeds expected count")
        }
        val events = mutableListOf<RecoveryEvent>()
        val fragments = fragmentValues.mapNotNull { fragmentValue ->
            try {
                decodeFragment(fragmentValue, expected)
            } catch (_: IllegalArgumentException) {
                events += RecoveryEvent.DROPPED_CORRUPT_FRAGMENT
                null
            } catch (_: StatePersistenceException) {
                events += RecoveryEvent.DROPPED_CORRUPT_FRAGMENT
                null
            }
        }
        val snapshot = try {
            TransferSnapshot(
                transferId = state.string("transfer_id"),
                objectId = state.string("object_id"),
                representationId = state.string("representation_id"),
                expectedFragments = expected,
                capacityBytes = state.long("capacity_bytes"),
                fragments = fragments.sortedBy { it.chunkIndex },
            ).also { it.validate() }
        } catch (error: IllegalArgumentException) {
            throw StatePersistenceException("transfer state validation failed", error)
        }
        return DecodedState(snapshot, events)
    }

    private fun decodeFragment(value: Any?, expected: Int): VerifiedFragment {
        val fragment = value.asStringMap("fragment")
        if (fragment.keys != FRAGMENT_KEYS) {
            throw StatePersistenceException("fragment fields are invalid")
        }
        return VerifiedFragment(
            objectId = fragment.string("object_id"),
            representationId = fragment.string("representation_id"),
            chunkIndex = fragment.long("chunk_index").toBoundedInt(
                "chunk_index",
                0,
                expected - 1,
            ),
            sha256 = fragment.string("sha256"),
            payloadBase64 = fragment.string("payload_b64"),
        ).also { it.validate(expected) }
    }

    private fun quarantinePrimary() {
        val prefix = Files.newInputStream(primary).use { input ->
            input.readNBytes((maxDocumentBytes + 1).toInt())
        }
        val digest = CanonicalJson.sha256Hex(prefix)
        var suffix = 0
        while (true) {
            val candidate = safePath("$PRIMARY_FILE.corrupt.$digest.$suffix")
            if (!Files.exists(candidate)) {
                moveReplace(primary, candidate)
                return
            }
            suffix++
        }
    }

    private fun writeAndSync(path: Path, bytes: ByteArray) {
        FileOutputStream(path.toFile()).use { output ->
            output.write(bytes)
            output.flush()
            output.fd.sync()
        }
    }

    private fun syncFile(path: Path) {
        FileChannel.open(path, StandardOpenOption.WRITE).use { it.force(true) }
    }

    private fun moveReplace(source: Path, target: Path) {
        try {
            Files.move(
                source,
                target,
                StandardCopyOption.ATOMIC_MOVE,
                StandardCopyOption.REPLACE_EXISTING,
            )
        } catch (_: AtomicMoveNotSupportedException) {
            Files.move(source, target, StandardCopyOption.REPLACE_EXISTING)
        }
    }

    private fun syncDirectoryBestEffort() {
        try {
            FileChannel.open(root, StandardOpenOption.READ).use { it.force(true) }
        } catch (_: IOException) {
            // Android/JVM filesystems differ on directory handles. The data
            // file itself is fsynced before atomic replacement in all cases.
        }
    }

    private fun safePath(fileName: String): Path {
        val candidate = root.resolve(fileName).normalize()
        require(candidate.parent == root) { "state path escaped app-private root" }
        return candidate
    }

    private fun TransferSnapshot.toJson(): Map<String, Any?> =
        linkedMapOf(
            "capacity_bytes" to capacityBytes,
            "expected_fragments" to expectedFragments,
            "fragments" to fragments.sortedBy { it.chunkIndex }.map { fragment ->
                linkedMapOf(
                    "chunk_index" to fragment.chunkIndex,
                    "object_id" to fragment.objectId,
                    "payload_b64" to fragment.payloadBase64,
                    "representation_id" to fragment.representationId,
                    "sha256" to fragment.sha256,
                )
            },
            "object_id" to objectId,
            "representation_id" to representationId,
            "transfer_id" to transferId,
        )

    private fun Any?.asStringMap(label: String): Map<String, Any?> {
        val map = this as? Map<*, *>
            ?: throw StatePersistenceException("$label must be an object")
        return map.entries.associate { (key, value) ->
            (key as? String
                ?: throw StatePersistenceException("$label contains a non-string key")) to value
        }
    }

    private fun Map<String, Any?>.string(key: String): String =
        this[key] as? String
            ?: throw StatePersistenceException("$key must be a string")

    private fun Map<String, Any?>.long(key: String): Long =
        this[key] as? Long
            ?: throw StatePersistenceException("$key must be an integer")

    private fun Long.toBoundedInt(label: String, minimum: Int, maximum: Int): Int {
        if (this !in minimum.toLong()..maximum.toLong()) {
            throw StatePersistenceException("$label is outside the supported range")
        }
        return toInt()
    }

    private data class DecodedState(
        val snapshot: TransferSnapshot,
        val events: List<RecoveryEvent>,
    )

    private companion object {
        const val PRIMARY_FILE = "transfer-state.json"
        const val ENVELOPE_SCHEMA = "shongket.android-state.v1.0"
        val ENVELOPE_KEYS = setOf("document_checksum", "schema", "state")
        val STATE_KEYS = setOf(
            "capacity_bytes",
            "expected_fragments",
            "fragments",
            "object_id",
            "representation_id",
            "transfer_id",
        )
        val FRAGMENT_KEYS = setOf(
            "chunk_index",
            "object_id",
            "payload_b64",
            "representation_id",
            "sha256",
        )
    }
}
