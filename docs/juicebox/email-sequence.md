⏺ How Juicebox (and Similar Platforms) Send Email Sequences                                                                                                                                      
                                                                                                                                                                                                 
  The Flow                                                                                                                                                                                       
                                                                                                                                                                                                 
  1. FIND EMAIL                                                                                                                                                                                  
     Profile in DB → lookup verified email (data providers / LinkedIn match)                                                                                                                     
          ↓                                                                                                                                                                                      
  2. BUILD SEQUENCE (multi-step campaign)                                                                                                                                                        
     Step 1: Cold outreach email (Day 0)                                                                                                                                                         
     Step 2: Follow-up if no reply (Day 3)                                                                                                                                                       
     Step 3: Hiring manager email (Day 7)                                                                                                                                                        
     Step 4: LinkedIn connection request (Day 10)
          ↓
  3. PERSONALIZE
     AI generates email using dynamic tokens:
     {first_name}, {current_title}, {company}, {skills}, {role_context}
          ↓
  4. SEND via connected mailbox
     User connects their Gmail/Outlook → sends FROM their real inbox
     (not from Juicebox servers — critical for deliverability)
          ↓
  5. TRACK & REACT
     Open tracking → Reply detection → Auto-stop sequence on reply
     Analytics: open rate, click rate, reply rate, bounce rate

  How They Find Emails

  ┌──────────────────────┬─────────────────────────────────────────────────────────────────────────┐
  │        Method        │                                 Source                                  │
  ├──────────────────────┼─────────────────────────────────────────────────────────────────────────┤
  │ Data providers       │ People Data Labs, Apollo, Clearbit return verified work/personal emails │
  ├──────────────────────┼─────────────────────────────────────────────────────────────────────────┤
  │ LinkedIn match       │ Profile URL → Proxycurl/PDL → email                                     │
  ├──────────────────────┼─────────────────────────────────────────────────────────────────────────┤
  │ GitHub public email  │ Available via GitHub API for ~30% of users                              │
  ├──────────────────────┼─────────────────────────────────────────────────────────────────────────┤
  │ Pattern guessing     │ {first}.{last}@company.com + SMTP verification                          │
  ├──────────────────────┼─────────────────────────────────────────────────────────────────────────┤
  │ Enrichment waterfall │ Try Provider A → if no email → try Provider B → try Provider C          │
  └──────────────────────┴─────────────────────────────────────────────────────────────────────────┘

  Email Infrastructure (How They Avoid Spam)

  They don't send from their own servers. The user connects their real mailbox:

  User's Gmail/Google Workspace  ──→  OAuth connect to Juicebox
  User's Outlook/O365            ──→  OAuth connect to Juicebox
  Custom SMTP                    ──→  SMTP credentials

  Juicebox sends emails through the user's own inbox using OAuth/SMTP, so it looks like a normal email from a real person.

  Deliverability stack:

  ┌───────────────────────┬──────────────────────────────────────────────────────────────────────────────────────────────┐
  │         Layer         │                                         What It Does                                         │
  ├───────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────┤
  │ SPF/DKIM/DMARC        │ DNS records proving the sender is legit (required by Gmail/Outlook in 2025+)                 │
  ├───────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Email warmup          │ New domains start at 5-10 emails/day, ramp up over 4-6 weeks                                 │
  ├───────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Warmup networks       │ Tools like MailReach/Instantly send/open/reply between 20k+ real inboxes to build reputation │
  ├───────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Rate limiting         │ Juicebox agents cap at ~35 emails/day per mailbox                                            │
  ├───────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Reply detection       │ Auto-stops sequence when candidate replies (reduces spam complaints)                         │
  ├───────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Bounce handling       │ Skip invalid emails, keep bounce rate <2%                                                    │
  ├───────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────┤
  │ One-click unsubscribe │ Required by Gmail/Yahoo for bulk senders (RFC 8058)                                          │
  └───────────────────────┴──────────────────────────────────────────────────────────────────────────────────────────────┘

  Tools the Industry Uses

  ┌───────────────────────────┬─────────────────────────────────────────────┐
  │         Category          │                    Tools                    │
  ├───────────────────────────┼─────────────────────────────────────────────┤
  │ Sequence sending          │ Juicebox, Gem, Instantly, Smartlead, Apollo │
  ├───────────────────────────┼─────────────────────────────────────────────┤
  │ Email warmup              │ MailReach, Instantly, Warmbox, Mailwarm     │
  ├───────────────────────────┼─────────────────────────────────────────────┤
  │ Email finding             │ Apollo, Hunter.io, Clearbit, PDL, Proxycurl │
  ├───────────────────────────┼─────────────────────────────────────────────┤
  │ Email verification        │ ZeroBounce, NeverBounce, MillionVerifier    │
  ├───────────────────────────┼─────────────────────────────────────────────┤
  │ Deliverability monitoring │ MailReach, GlockApps                        │
  └───────────────────────────┴─────────────────────────────────────────────┘

  Key Numbers

  - 35 emails/day per mailbox (Juicebox agent limit)
  - 14+ days warmup before sending campaigns
  - <2% bounce rate required by Gmail/Yahoocan we build this 
  - <0.3% spam complaints required to stay out of spam folder
  - 3x reply rate claimed by Juicebox vs manual outreach

  Sources:
  - https://juicebox.ai/outreach
  - https://juicebox.ai/agent
  - https://instantly.ai/blog/how-to-achieve-90-cold-email-deliverability-in-2025/
  - https://www.mailreach.co