from enum import Enum


class Tags(str, Enum):
    Health = "Health"
    User = "User"
    Organization = "Organization"
    Project = "Project"
    DeveloperProfile = "Developer Profile"
    Ingestion = "Ingestion"
    Mailbox = "Mailbox"
    EmailTemplate = "Email Template"
    Campaign = "Campaign"
    Tracking = "Tracking"
    EmailEnrichment = "Email Enrichment"
    Billing = "Billing"
