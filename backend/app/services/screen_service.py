from app.schemas.screen import (
    DesignTokens,
    ResponsiveRule,
    ScreenComponent,
    ScreenLayout,
    ScreenResponse,
    ScreenSection,
)


class ScreenService:
    @staticmethod
    def generate(requirement: str) -> ScreenResponse:
        return ScreenResponse(
            screen_name="Domestic Fund Transfer",
            screen_description=(
                "Transfer funds to a registered beneficiary."
            ),
            layout=ScreenLayout(
                type="single-column",
                max_width="960px",
                section_gap="24px",
            ),
            sections=[
                ScreenSection(
                    id="transfer-details",
                    title="Transfer Details",
                    description=(
                        "Select accounts and enter transfer information."
                    ),
                    layout="two-column",
                    components=[
                        ScreenComponent(
                            id="source-account",
                            type="Select",
                            label="From account",
                            placeholder="Select an account",
                            required=True,
                        ),
                        ScreenComponent(
                            id="available-balance",
                            type="SummaryCard",
                            label="Available balance",
                            value="Balance shown here",
                        ),
                        ScreenComponent(
                            id="beneficiary",
                            type="Select",
                            label="Beneficiary",
                            placeholder=(
                                "Select a registered beneficiary"
                            ),
                            required=True,
                        ),
                        ScreenComponent(
                            id="transfer-amount",
                            type="NumberInput",
                            label="Transfer amount",
                            placeholder="Enter amount",
                            required=True,
                        ),
                        ScreenComponent(
                            id="remarks",
                            type="TextArea",
                            label="Remarks",
                            placeholder="Add optional remarks",
                        ),
                    ],
                ),
                ScreenSection(
                    id="review-actions",
                    title="Review and Confirm",
                    description=(
                        "Review the transfer before confirmation."
                    ),
                    layout="single-column",
                    components=[
                        ScreenComponent(
                            id="transfer-summary",
                            type="Card",
                            label="Transfer summary",
                        ),
                        ScreenComponent(
                            id="confirm-transfer",
                            type="Button",
                            label="Confirm transfer",
                            variant="primary",
                        ),
                        ScreenComponent(
                            id="cancel-transfer",
                            type="Button",
                            label="Cancel",
                            variant="secondary",
                        ),
                    ],
                ),
            ],
            design_tokens=DesignTokens(),
            responsive_rules=[
                ResponsiveRule(
                    breakpoint="768px",
                    behavior=(
                        "Convert multi-column sections to one column."
                    ),
                )
            ],
        )
