from pydantic import BaseModel


class ComplianceIssueSchema(BaseModel):
    title: str = ""
    description: str = ""
    severity: str = "low"
    rule_numbers: list[str] | None = None
    rule_titles: list[str] | None = None
    legal_basis: str | None = None
    ocr_evidence: str | None = None


class ComplianceAnalysisSchema(BaseModel):
    product_name: str = ""
    mrp: str = ""
    net_quantity: str = ""
    manufacturer: str = ""
    address: str = ""
    packing_date: str = ""
    customer_care: str = ""
    missing_information: list[str] = []
    possible_issues: list[ComplianceIssueSchema] = []
