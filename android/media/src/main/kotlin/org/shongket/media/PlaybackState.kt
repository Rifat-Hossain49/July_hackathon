package org.shongket.media

data class RepresentationUiState(
    val id: RepresentationId,
    val availability: Availability,
    val actionable: Boolean,
    val reasonCode: String?,
)

object PlaybackStateResolver {
    fun resolve(
        manifest: MediaManifest,
        completeRepresentations: Set<RepresentationId>,
    ): List<RepresentationUiState> {
        manifest.validate()
        return manifest.representations.map { record ->
            when {
                record.availability == Availability.UNAVAILABLE ->
                    RepresentationUiState(
                        record.id,
                        Availability.UNAVAILABLE,
                        false,
                        record.reasonCode,
                    )
                record.id in completeRepresentations ->
                    RepresentationUiState(record.id, Availability.AVAILABLE, true, null)
                else ->
                    RepresentationUiState(
                        record.id,
                        Availability.INCOMPLETE,
                        false,
                        "TRANSFER_INCOMPLETE",
                    )
            }
        }
    }
}
