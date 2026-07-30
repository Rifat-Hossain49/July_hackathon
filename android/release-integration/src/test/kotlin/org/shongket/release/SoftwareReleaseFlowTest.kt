package org.shongket.release

import java.nio.file.Files
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.shongket.media.DeliveryItem

class SoftwareReleaseFlowTest {
    @Test
    fun interactiveDemoFlowRestartsResumesAndExportsOnlyCodes() {
        val directory = Files.createTempDirectory("shongket-demo-controller-")
        try {
            val first = DemoController(directory)
            first.createFixture()
            first.confirmCapsule(
                message = "পানি প্রয়োজন",
                location = "নদীর পাশের গ্রাম",
                isPrivate = true,
                explicitConsent = false,
            )
            assertEquals("CONSENT_REQUIRED", first.state().lastErrorCode)
            first.confirmCapsule(
                message = "পানি প্রয়োজন",
                location = "নদীর পাশের গ্রাম",
                isPrivate = true,
                explicitConsent = true,
            )
            first.selectSimulatedPeer()
            first.startTransfer()
            first.interruptTransfer()
            assertEquals(50, first.state().progressPercent)

            val restarted = DemoController(directory)
            assertEquals(DemoStage.INTERRUPTED, restarted.state().stage)
            restarted.resumeTransfer()
            restarted.exportDiagnostics()
            val complete = restarted.state()
            assertEquals(DemoStage.RECEIVED, complete.stage)
            assertEquals(100, complete.progressPercent)
            assertTrue(complete.receivedVerified)
            assertTrue(complete.diagnosticJson?.contains("RECONSTRUCTION_VERIFIED") == true)
            assertFalse(complete.diagnosticJson?.contains("নদীর পাশের গ্রাম") == true)
        } finally {
            check(directory.toFile().deleteRecursively())
        }
    }

    @Test
    fun completeSoftwareFlowPreservesSourceAndResumesMissingOnly() {
        val directory = Files.createTempDirectory("shongket-release-")
        try {
            val source = ByteArray(70_000) { (it % 251).toByte() }
            val evidence = SoftwareReleaseFlow().runDeterministicFixture(
                directory,
                source,
                explicitPrivateForwardConsent = true,
            )
            assertArrayEquals(source, evidence.sourceBytesAfterFlow)
            assertEquals(listOf(1), evidence.restartMissingIndexes)
            assertEquals(2, evidence.storedFragments)
            assertTrue(evidence.humanConfirmed)
            assertEquals(DeliveryItem.CAPSULE, evidence.orderedDelivery.first())
            assertEquals(DeliveryItem.MANIFEST, evidence.orderedDelivery[1])
            assertTrue(evidence.diagnosticJson.contains("FLOW_COMPLETE"))
            assertFalse(evidence.diagnosticJson.contains("operator supplied location"))
        } finally {
            check(directory.toFile().deleteRecursively())
        }
    }

    @Test(expected = IllegalStateException::class)
    fun privateFlowCannotProceedWithoutExplicitConsent() {
        val directory = Files.createTempDirectory("shongket-release-denied-")
        try {
            SoftwareReleaseFlow().runDeterministicFixture(
                directory,
                ByteArray(70_000) { 1 },
                explicitPrivateForwardConsent = false,
            )
        } finally {
            check(directory.toFile().deleteRecursively())
        }
    }
}
