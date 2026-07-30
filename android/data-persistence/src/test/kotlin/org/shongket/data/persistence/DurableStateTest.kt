package org.shongket.data.persistence

import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardOpenOption
import kotlin.io.path.exists
import kotlin.io.path.listDirectoryEntries
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.shongket.core.conformance.CanonicalJson

class DurableStateTest {
    @Test
    fun processRestartRequestsOnlyMissingFragmentsWithoutDuplicates() = withDirectory {
        val first = DurableTransferRepository(AppPrivateStateStore(it))
        first.begin("transfer-1", OBJECT_ID, "original", 4, 128)
        assertTrue(first.ingest(fragment(0, "zero")) is IngestResult.Accepted)
        assertTrue(first.ingest(fragment(2, "two")) is IngestResult.Accepted)

        val restarted = DurableTransferRepository(AppPrivateStateStore(it))
        assertEquals(listOf(1, 3), restarted.resumePlan()?.missingIndexes)
        assertEquals(IngestResult.Duplicate, restarted.ingest(fragment(0, "zero")))
        assertEquals(2, restarted.currentSnapshot()?.fragments?.size)
    }

    @Test
    fun lifecycleRecoveryUsesDurableStateAndSmallSavedIdentifier() = withDirectory {
        val first = DurableTransferRepository(AppPrivateStateStore(it))
        first.begin("transfer-2", OBJECT_ID, "original", 3, 128)
        first.ingest(fragment(1, "one"))

        val restarted = DurableTransferRepository(AppPrivateStateStore(it))
        val resumed = mutableListOf<ResumePlan>()
        val recovery = TransferLifecycleCoordinator(restarted).recover(
            savedUi = SavedUiIdentifiers(activeTransferId = "stale-transfer"),
            backgroundTransfer = BackgroundTransferPort(resumed::add),
        )

        assertEquals("transfer-2", recovery.activeTransferId)
        assertEquals(1, recovery.verifiedFragments)
        assertEquals(3, recovery.expectedFragments)
        assertEquals(listOf(0, 2), recovery.missingIndexes)
        assertEquals(listOf(0, 2), resumed.single().missingIndexes)
    }

    @Test
    fun outOfBudgetRefusesBeforeMutationAndNeverEvicts() = withDirectory {
        val repository = DurableTransferRepository(AppPrivateStateStore(it))
        repository.begin("transfer-3", OBJECT_ID, "original", 3, 4)
        repository.ingest(fragment(0, "abc"))
        val before = repository.currentSnapshot()

        val result = repository.ingest(fragment(1, "de"))

        assertEquals(IngestResult.OutOfBudget(3, 4, 2), result)
        assertEquals(before, repository.currentSnapshot())
        val reopened = DurableTransferRepository(AppPrivateStateStore(it))
        assertEquals(before, reopened.currentSnapshot())
        assertEquals(listOf(0), reopened.currentSnapshot()?.fragments?.map { f -> f.chunkIndex })
    }

    @Test
    fun truncatedTemporaryFileIsDiscardedWithoutChangingPrimary() = withDirectory {
        val repository = DurableTransferRepository(AppPrivateStateStore(it))
        repository.begin("transfer-4", OBJECT_ID, "original", 2, 64)
        repository.ingest(fragment(0, "safe"))
        Files.writeString(
            it.resolve("transfer-state.json.tmp"),
            """{"truncated":""",
            StandardOpenOption.CREATE,
            StandardOpenOption.TRUNCATE_EXISTING,
        )

        val result = AppPrivateStateStore(it).load()

        assertEquals(listOf(RecoveryEvent.DISCARDED_TRUNCATED_TEMP), result.events)
        assertEquals(listOf(0), result.snapshot?.fragments?.map { f -> f.chunkIndex })
        assertFalse(it.resolve("transfer-state.json.tmp").exists())
    }

    @Test
    fun corruptPrimaryIsQuarantinedAndLastGoodLoads() = withDirectory {
        val repository = DurableTransferRepository(AppPrivateStateStore(it))
        repository.begin("transfer-5", OBJECT_ID, "original", 3, 64)
        repository.ingest(fragment(0, "first"))
        repository.ingest(fragment(1, "second"))
        Files.writeString(
            it.resolve("transfer-state.json"),
            """{"broken":true}""",
            StandardOpenOption.TRUNCATE_EXISTING,
        )

        val loaded = AppPrivateStateStore(it).load()

        assertEquals(listOf(0), loaded.snapshot?.fragments?.map { f -> f.chunkIndex })
        assertEquals(
            listOf(
                RecoveryEvent.QUARANTINED_PRIMARY,
                RecoveryEvent.LOADED_LAST_GOOD,
            ),
            loaded.events,
        )
        assertTrue(
            it.listDirectoryEntries("transfer-state.json.corrupt.*").size == 1,
        )
    }

    @Test
    fun corruptFirstSnapshotIsQuarantinedAndAppCanStartEmpty() = withDirectory {
        val repository = DurableTransferRepository(AppPrivateStateStore(it))
        repository.begin("transfer-empty", OBJECT_ID, "original", 2, 64)
        Files.writeString(
            it.resolve("transfer-state.json"),
            """{"broken":true}""",
            StandardOpenOption.TRUNCATE_EXISTING,
        )

        val loaded = AppPrivateStateStore(it).load()

        assertEquals(null, loaded.snapshot)
        assertEquals(listOf(RecoveryEvent.QUARANTINED_PRIMARY), loaded.events)
        assertTrue(it.listDirectoryEntries("transfer-state.json.corrupt.*").size == 1)
    }

    @Test
    fun corruptFragmentIsDroppedButIntactFragmentsSurvive() = withDirectory {
        val repository = DurableTransferRepository(AppPrivateStateStore(it))
        repository.begin("transfer-6", OBJECT_ID, "original", 3, 64)
        repository.ingest(fragment(0, "first"))
        repository.ingest(fragment(1, "second"))
        val path = it.resolve("transfer-state.json")
        val document = CanonicalJson.parse(Files.readString(path)).asMutableMap()
        val state = document["state"].asMutableMap()
        val fragments = (state["fragments"] as List<*>)
            .map { value -> value.asMutableMap() }
            .toMutableList()
        fragments[1]["sha256"] = "0".repeat(64)
        state["fragments"] = fragments
        document["state"] = state
        document["document_checksum"] = CanonicalJson.sha256Hex(
            linkedMapOf("schema" to document["schema"], "state" to state),
        )
        Files.writeString(path, CanonicalJson.encode(document))

        val loaded = AppPrivateStateStore(it).load()

        assertEquals(listOf(0), loaded.snapshot?.fragments?.map { f -> f.chunkIndex })
        assertEquals(listOf(RecoveryEvent.DROPPED_CORRUPT_FRAGMENT), loaded.events)
    }

    @Test
    fun conflictingDuplicateIsRejectedWithoutMutation() = withDirectory {
        val repository = DurableTransferRepository(AppPrivateStateStore(it))
        repository.begin("transfer-7", OBJECT_ID, "original", 2, 64)
        repository.ingest(fragment(0, "first"))
        val before = repository.currentSnapshot()

        assertEquals(
            IngestResult.IntegrityRejected,
            repository.ingest(fragment(0, "changed")),
        )
        assertEquals(before, repository.currentSnapshot())
    }

    private fun fragment(index: Int, text: String): VerifiedFragment =
        VerifiedFragment.fromBytes(
            objectId = OBJECT_ID,
            representationId = "original",
            chunkIndex = index,
            payload = text.toByteArray(),
        )

    private fun Any?.asMutableMap(): MutableMap<String, Any?> {
        val source = this as Map<*, *>
        return source.entries.associate { (key, value) -> key as String to value }.toMutableMap()
    }

    private fun withDirectory(block: (Path) -> Unit) {
        val directory = Files.createTempDirectory("shongket-state-")
        try {
            block(directory)
        } finally {
            check(directory.toFile().deleteRecursively())
        }
    }

    private companion object {
        const val OBJECT_ID =
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }
}
