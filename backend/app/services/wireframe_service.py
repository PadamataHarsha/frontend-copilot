from app.schemas.wireframe import WireframeResponse, Section


class WireframeService:
    @staticmethod
    def generate(requirement: str) -> WireframeResponse:
        return WireframeResponse(
            screen_name="Leave Management",
            sections=[
                Section(
                    title="Leave Balance",
                    components=["Card"]
                ),
                Section(
                    title="Apply Leave",
                    components=["Form"]
                ),
                Section(
                    title="Leave History",
                    components=["Table"]
                )
            ]
        )