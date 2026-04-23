from enum import Enum


class Tags(str, Enum):
    Health = "Health"
    DeveloperProfile = "Developer Profile"
    Ingestion = "Ingestion"
    Mailbox = "Mailbox"
    EmailTemplate = "Email Template"
    Campaign = "Campaign"
    Tracking = "Tracking"
    EmailEnrichment = "Email Enrichment"
