"""Batch 3: Finance (5) + Marketing (5)."""
import json, pathlib
DS = pathlib.Path(__file__).resolve().parent.parent / "tests/benchmark/benchmark_dataset.json"

NEW = [
  # ── FINANCE (5) ──
  {"id":"B071","name":"Finance - Investment Analyst","category":"finance",
   "cv_text":"Michael Chang\nInvestment Analyst\n\nExperience:\nInvestment Analyst, Goldman Partners, 2020 - Present\n- Financial modeling and DCF valuation for M&A transactions\n- Bloomberg Terminal and Capital IQ for market analysis\n- Prepared investment memos and board presentations\n- Portfolio analysis across equities, fixed income, and derivatives\n\nSkills: Financial Modeling, DCF, Bloomberg, Excel, PowerPoint, Python, SQL\nEducation: MBA Finance, Wharton, 2020\nCFA Level III Candidate",
   "job_description":"Investment Analyst. Financial modeling, DCF valuation, Bloomberg Terminal, Excel. CFA preferred. M&A experience.",
   "expected":{"keyword_score":{"min":30,"max":80},"ats_score":{"min":40,"max":80},"final_score":{"min":40,"max":80}}},

  {"id":"B072","name":"Finance - Risk Manager","category":"finance",
   "cv_text":"Sarah Williams\nRisk Manager\n\nExperience:\nSenior Risk Manager, JP Asset Management, 2018 - Present\n- Market risk and credit risk assessment\n- VaR calculations and stress testing\n- Basel III/IV regulatory compliance\n- Risk reporting to senior management and board\n- Python and R for quantitative risk modeling\n\nSkills: Risk Management, VaR, Stress Testing, Basel III, Python, R, SQL, Excel\nEducation: MS Financial Engineering, Columbia, 2018\nFRM Certified",
   "job_description":"Risk Manager. Market risk, credit risk, VaR, stress testing. Basel III compliance. Python/R for modeling. FRM preferred.",
   "expected":{"keyword_score":{"min":35,"max":80},"ats_score":{"min":45,"max":80},"final_score":{"min":45,"max":80}}},

  {"id":"B073","name":"Finance - FinTech Developer","category":"finance",
   "cv_text":"James Liu\nFinTech Software Engineer\n\nExperience:\nSenior Engineer, PaymentTech, 2019 - Present\n- Built payment processing system handling $2B annually\n- Python/FastAPI microservices with event-driven architecture\n- PCI-DSS compliance implementation\n- Real-time fraud detection with ML models\n- PostgreSQL and Redis for transaction data\n\nSkills: Python, FastAPI, PostgreSQL, Redis, Kafka, Docker, AWS, PCI-DSS\nEducation: BS Computer Science + Minor Finance, 2019",
   "job_description":"FinTech Engineer. Python, payment systems, PCI-DSS, microservices, PostgreSQL. Financial services experience required.",
   "expected":{"keyword_score":{"min":30,"max":75},"ats_score":{"min":45,"max":85},"final_score":{"min":45,"max":80}}},

  {"id":"B074","name":"Finance - Quant Analyst","category":"finance",
   "cv_text":"Anna Petrova\nQuantitative Analyst\n\nExperience:\nQuant Analyst, HedgeFund Capital, 2019 - Present\n- Developed algorithmic trading strategies with Python\n- Statistical modeling and time series analysis\n- Monte Carlo simulations for options pricing\n- High-frequency data analysis with pandas and numpy\n- C++ optimization for latency-critical systems\n\nSkills: Python, C++, R, pandas, numpy, scipy, SQL, Bloomberg, MATLAB\nEducation: PhD Applied Mathematics, 2019",
   "job_description":"Quantitative Analyst. Python, C++, statistical modeling, time series, algorithmic trading. PhD in STEM preferred.",
   "expected":{"keyword_score":{"min":25,"max":75},"ats_score":{"min":45,"max":80},"final_score":{"min":40,"max":80}}},

  {"id":"B075","name":"Finance Analyst vs Dev JD","category":"cross_sector",
   "cv_text":"Tom Richards\nFinancial Analyst\n\nExperience:\nFinancial Analyst, ConsultingCo, 2020 - Present\n- Budget forecasting and variance analysis\n- Excel financial models and PowerPoint presentations\n- Quarterly earnings reports\n- Stakeholder communication\n\nSkills: Excel, PowerPoint, Financial Modeling, SAP, Tableau\nEducation: BBA Finance, 2020",
   "job_description":"Full Stack Developer. React, Node.js, Python, PostgreSQL, Docker, AWS, CI/CD.",
   "expected":{"keyword_score":{"min":0,"max":15},"ats_score":{"min":20,"max":60},"final_score":{"min":20,"max":55}}},

  # ── MARKETING (5) ──
  {"id":"B076","name":"Marketing - Digital Marketing Manager","category":"marketing",
   "cv_text":"Laura Garcia\nDigital Marketing Manager\n\nExperience:\nDigital Marketing Manager, BrandCo, 2019 - Present\n- Google Ads and Facebook Ads campaign management ($500K/month budget)\n- SEO/SEM strategy increasing organic traffic by 200%\n- Email marketing automation with HubSpot and Mailchimp\n- Google Analytics and Data Studio reporting\n- Social media strategy across Instagram, LinkedIn, TikTok\n- A/B testing and conversion rate optimization\n\nSkills: Google Ads, Facebook Ads, SEO, Google Analytics, HubSpot, Mailchimp, Canva\nEducation: BA Marketing, 2019",
   "job_description":"Digital Marketing Manager. Google Ads, Facebook Ads, SEO/SEM, email marketing, analytics. 3+ years.",
   "expected":{"keyword_score":{"min":30,"max":80},"ats_score":{"min":40,"max":80},"final_score":{"min":40,"max":80}}},

  {"id":"B077","name":"Marketing - Content Strategist","category":"marketing",
   "cv_text":"Rachel Kim\nContent Strategist\n\nExperience:\nSenior Content Strategist, MediaCo, 2020 - Present\n- Content calendar management for 5 brands\n- Blog writing, copywriting, and editorial planning\n- WordPress and Webflow CMS management\n- SEO content optimization with Ahrefs and SEMrush\n- Video content strategy for YouTube (100K+ subscribers)\n\nSkills: Content Strategy, Copywriting, SEO, WordPress, Ahrefs, SEMrush, Canva, Video Editing\nEducation: BA Communications, 2020",
   "job_description":"Content Strategist. Content planning, copywriting, SEO, CMS (WordPress), video content. Analytics experience.",
   "expected":{"keyword_score":{"min":25,"max":75},"ats_score":{"min":40,"max":80},"final_score":{"min":40,"max":75}}},

  {"id":"B078","name":"Marketing - Growth Hacker","category":"marketing",
   "cv_text":"Alex Turner\nGrowth Marketing Lead\n\nExperience:\nGrowth Lead, SaaS Startup, 2021 - Present\n- Grew MRR from $50K to $500K in 18 months\n- Product-led growth strategy implementation\n- Mixpanel and Amplitude analytics\n- Landing page optimization (Unbounce)\n- Referral program design increasing user acquisition by 300%\n- SQL queries for cohort analysis\n\nSkills: Growth Marketing, PLG, Mixpanel, Amplitude, SQL, Google Ads, Landing Pages\nEducation: BS Business Analytics, 2021",
   "job_description":"Growth Marketing Manager. PLG, analytics (Mixpanel/Amplitude), paid acquisition, SQL. SaaS experience.",
   "expected":{"keyword_score":{"min":25,"max":75},"ats_score":{"min":40,"max":80},"final_score":{"min":40,"max":75}}},

  {"id":"B079","name":"Marketing - Brand Manager","category":"marketing",
   "cv_text":"Sophia Anderson\nBrand Manager\n\nExperience:\nBrand Manager, FMCG Corp, 2019 - Present\n- Brand strategy for $100M consumer product portfolio\n- Market research and competitive analysis\n- Product launch campaigns across TV, digital, print\n- P&L management and pricing strategy\n- Agency management (creative, media, PR)\n\nSkills: Brand Strategy, Market Research, P&L Management, Project Management, PowerPoint\nEducation: MBA Marketing, 2019",
   "job_description":"Brand Manager. Brand strategy, market research, P&L management, campaign management. FMCG experience preferred.",
   "expected":{"keyword_score":{"min":25,"max":70},"ats_score":{"min":40,"max":80},"final_score":{"min":40,"max":75}}},

  {"id":"B080","name":"Marketing Manager vs Dev JD","category":"cross_sector",
   "cv_text":"Chris Martin\nMarketing Manager\n\nExperience:\nMarketing Manager, RetailCo, 2020 - Present\n- Campaign management and budget allocation\n- Social media strategy\n- Brand awareness initiatives\n- Event planning and sponsorships\n\nSkills: Marketing Strategy, Social Media, Event Planning, PowerPoint, Excel\nEducation: BA Communications, 2020",
   "job_description":"Backend Developer. Python, FastAPI, PostgreSQL, Docker, Kubernetes, AWS, CI/CD pipelines.",
   "expected":{"keyword_score":{"min":0,"max":15},"ats_score":{"min":20,"max":60},"final_score":{"min":20,"max":55}}},
]

with open(DS, "r", encoding="utf-8") as f:
    data = json.load(f)
existing = {e["id"] for e in data["entries"]}
added = 0
for e in NEW:
    if e["id"] not in existing:
        data["entries"].append(e)
        added += 1
with open(DS, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f"Added {added}, total: {len(data['entries'])}")
