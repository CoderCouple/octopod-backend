⏺ LinkedIn Data — Practical Options                                                                                                                                                              
                                         
  1. Buy from Data Providers (What Juicebox does)                                                                                                                                                
   
  ┌────────────────────────┬──────────┬──────────────────────────────┬────────────────────────┐                                                                                                  
  │        Provider        │ Profiles │            Price             │         Notes          │
  ├────────────────────────┼──────────┼──────────────────────────────┼────────────────────────┤
  │ People Data Labs       │ 1.5B+    │ Pay per record (~$0.01-0.10) │ Most popular, bulk API │
  ├────────────────────────┼──────────┼──────────────────────────────┼────────────────────────┤
  │ Proxycurl              │ 500M+    │ $0.01/profile                │ Already in your .env   │
  ├────────────────────────┼──────────┼──────────────────────────────┼────────────────────────┤
  │ Coresignal             │ 700M+    │ Enterprise pricing           │ Real-time updates      │
  ├────────────────────────┼──────────┼──────────────────────────────┼────────────────────────┤
  │ Apollo.io              │ 275M+    │ Free tier available          │ Emails included        │
  ├────────────────────────┼──────────┼──────────────────────────────┼────────────────────────┤
  │ Clearbit (now HubSpot) │ 200M+    │ Enterprise                   │ Company + person data  │
  └────────────────────────┴──────────┴──────────────────────────────┴────────────────────────┘

  ┌────────────────────┬──────────┬────────────────┬───────────────────────────────────────┬────────────────────────────┬────────────────────────────────────────────────┐
  │      Provider      │ Profiles │  Per Profile   │             Monthly Plans             │   Cost for 100K profiles   │                     Notes                      │
  ├────────────────────┼──────────┼────────────────┼───────────────────────────────────────┼────────────────────────────┼────────────────────────────────────────────────┤
  │ People Data Labs   │ 1.5B+    │ $0.20–$0.28    │ From $98/mo (350 credits)             │ ~$20,000–$28,000           │ Best bulk coverage, enterprise deals for 100k+ │
  ├────────────────────┼──────────┼────────────────┼───────────────────────────────────────┼────────────────────────────┼────────────────────────────────────────────────┤
  │ Proxycurl          │ 500M+    │ ~$0.02–$0.10   │ From $49/mo (2,500 credits)           │ ~$2,000–$10,000            │ ⚠️ May be shutting down — founder moved on     │
  ├────────────────────┼──────────┼────────────────┼───────────────────────────────────────┼────────────────────────────┼────────────────────────────────────────────────┤
  │ Coresignal         │ 700M+    │ Custom         │ Datasets from $1,000; API from $49/mo │ ~$5,000–$50,000 (dataset)  │ Bulk dataset purchase, refreshed every 6hrs    │
  ├────────────────────┼──────────┼────────────────┼───────────────────────────────────────┼────────────────────────────┼────────────────────────────────────────────────┤
  │ Apollo.io          │ 275M+    │ ~$0.20/overage │ Free–$149/user/mo                     │ ~$20,000 (at overage rate) │ Free tier: 10 exports/mo; Basic: 5k credits/yr │
  ├────────────────────┼──────────┼────────────────┼───────────────────────────────────────┼────────────────────────────┼────────────────────────────────────────────────┤
  │ Clearbit (HubSpot) │ 200M+    │ Custom         │ Enterprise only                       │ ~$20,000–$100,000/yr       │ Best for company data enrichment               │
  └────────────────────┴──────────┴────────────────┴───────────────────────────────────────┴────────────────────────────┴────────────────────────────────────────────────┘

  For Octopod's Use Case (Developer Profiles)

  ┌───────────────────┬──────────────────────────────────────┬────────────────────┐
  │       Scale       │             Best Option              │     Est. Cost      │
  ├───────────────────┼──────────────────────────────────────┼────────────────────┤
  │ 1K profiles (MVP) │ Apollo.io free tier or Proxycurl     │ $0–$100            │
  ├───────────────────┼──────────────────────────────────────┼────────────────────┤
  │ 10K profiles      │ Proxycurl or Coresignal API          │ $200–$1,000        │
  ├───────────────────┼──────────────────────────────────────┼────────────────────┤
  │ 100K profiles     │ Coresignal dataset or PDL enterprise │ $5,000–$20,000     │
  ├───────────────────┼──────────────────────────────────────┼────────────────────┤
  │ 1M+ profiles      │ Coresignal/PDL bulk dataset deal     │ $20,000–$50,000/yr │
  └───────────────────┴──────────────────────────────────────┴────────────────────┘

  Cheapest Path

  1. Free: GitHub + HuggingFace APIs (what we already have — unlimited public data)
  2. $49/mo: Coresignal API or Proxycurl for LinkedIn enrichment of matched profiles only
  3. $1,000+: Coresignal bulk dataset for mass LinkedIn coverage

  Sources:
  - https://www.peopledatalabs.com/pricing/person
  - https://nubela.co/proxycurl/pricing.html
  - https://coresignal.com/pricing/
  - https://www.apollo.io/pricing


  This is the fastest and safest path. No scraping, no legal risk. You get structured JSON back.

  2. Proxycurl (Already Integrated)

  You already have PROXYCURL_API_KEY in your .env. One API call per profile:

  GET https://nubela.co/proxycurl/api/v2/linkedin?url=https://linkedin.com/in/johndoe

  Returns structured JSON: name, headline, experience, education, skills, etc. ~$0.01/profile.

  3. LinkedIn Official APIs

  - LinkedIn Marketing API — limited, mostly for ads
  - LinkedIn Recruiter — $10k+/yr, only via their UI, no bulk export
  - LinkedIn Sales Navigator — structured search but no bulk API

  Official APIs are very restricted — not viable for bulk collection.

  4. Direct Scraping (Risky)

  LinkedIn actively fights scraping with:
  - Rate limiting & IP bans
  - CAPTCHAs
  - Session detection
  - Legal action (LinkedIn v. hiQ Labs went to Supreme Court — hiQ won on public profiles, but LinkedIn still sends C&Ds)

  Tools people use despite risks:
  - Bright Data (proxy network + LinkedIn dataset)
  - PhantomBuster (browser automation)
  - Apify LinkedIn Scraper (cloud-based)
  - Custom Selenium/Playwright with residential proxies

  My Recommendation for Octopod

  Use Proxycurl — you already have it set up. The flow would be:

  1. Discover developers via GitHub/HuggingFace (free, public APIs)
  2. Match to LinkedIn URLs from their GitHub bio/website/email
  3. Enrich with Proxycurl only for matched profiles (~$0.01 each)

  This keeps costs low (you only pay for profiles you actually care about) and avoids any scraping risk. For 100k developer profiles, that's ~$1,000.
