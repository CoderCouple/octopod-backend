from enum import Enum


class Tags(str, Enum):
    Health = "Health"
    Organization = "Organization"
    Employee = "Employee"
    Employment = "Employment"
    Relationship = "Relationship"
    Claim = "Claim"
    Graph = "Graph"
    Timeline = "Timeline"
    Visibility = "Visibility"
    DeveloperProfile = "Developer Profile"
    Ingestion = "Ingestion"
