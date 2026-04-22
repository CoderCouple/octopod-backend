 ### Here's how Juicebox built their 800M+ profile database:                                                                                                                                        
                                                                                                                                                                                                 
  Data Sources (~30-60 sources)                                                                                                                                                                  
                                                                                                                                                                                                 
  They aggregate from publicly available professional data platforms:                                                                                                                            
  - LinkedIn — the bulk (scraped/purchased profile data)                                                                                                                                         
  - GitHub — developer profiles, repos, contributions
  - Stack Overflow — Q&A activity, reputation                                                                                                                                                    
  - Dribbble — designer portfolios                                                                                                                                                               
  - Crunchbase — founder/exec data                                                                                                                                                               
  - Academic repositories — research papers, university affiliations
  - Patent databases, job boards, personal websites, etc.

  How They Actually Do It

  1. Third-party data providers — They buy bulk profile datasets from data brokers (companies like People Data Labs, Proxycurl, Clearbit, etc. sell aggregated professional data at scale). This
  is the main way to get to 800M fast.
  2. Web scraping — Public profiles are crawled periodically. Every profile in their system "was scraped at some point."
  3. Entity resolution / deduplication — Same person appears on GitHub, LinkedIn, Stack Overflow → they merge into one unified profile (similar to what our profile_merge_service does).
  4. Infrastructure — AWS Glue for ETL preprocessing, Amazon OpenSearch (vector DB) for semantic search indexing. They reprocess hundreds of millions of profiles monthly.

  The Reality

  Nobody scrapes 800M profiles from scratch. The playbook is:
  - Buy bulk data from providers like People Data Labs (which claims 1.5B+ profiles)
  - Enrich with platform-specific scraping (GitHub, HuggingFace, etc.)
  - Deduplicate and merge across sources
  - Embed and index for semantic search

  Our Octopod approach (GitHub + HuggingFace ingestion → merge → embed → vector search) follows the same pattern, just focused on developer/ML profiles rather than all professionals.

  Sources:
  - https://juicebox.ai/peoplegpt
  - https://aws.amazon.com/blogs/big-data/juicebox-recruits-amazon-opensearch-service-for-improved-talent-search/
  - https://juicebox.ai/blog/company-data-and-talent-insights-just-got-a-major-upgrade
