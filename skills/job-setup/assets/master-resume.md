# Master resume template

<!--
How the master works

The master is one long file with everything you have done. It is never sent
anywhere. For each job, the agent copies it, keeps the entries and bullets
that fit that posting, and trims the rest to one page. This Markdown master
renders in the same layout as master-resume.tex:
  python3 skills/tailor-resume/scripts/md_to_tex.py copy.md -o copy.tex && tectonic copy.tex

Rules
- Put every job, project, research role, club role and award here, even small ones.
- The bullets outside alt blocks are your current best page: at most 3 per entry,
  and they fill one page. Add alternates inside an alt block. Each alternate says
  the same work with a different emphasis (scale, a tool, a result, the user).
  More alternates give the tailoring step more truthful ways to match a posting.
- Every number must be one you can explain in an interview. The agent never
  adds a metric, tool or experience that is not in this file.
- The Skills rows list tools you have really used; put extra rows and terms in an
  alt block so they stay in the bank without printing.
- The first bullet of each project says what the project is, as
  "<noun> that <does what>" near the start: "a web app that shows live arrival times".
- A hackathon win names the hackathon with its host school and the project count:
  "winning Best Civic Hack of 180 projects at Lakeside University's LakeHacks".
- Layout the converter and checkers read:
    ## Education   ### School | Location, then a line: Degree | Date
    ## Experience  ### Title | Dates, then a line: Company | Location, then - bullets
    ## Projects    ### [Name](https://url) | Stack, then - bullets
    ## Technical Skills   - Label: a, b, c
  Alternates sit between <!-- alt --> and <!-- /alt -->. **bold** prints bold.
- Jordan Lee is a placeholder persona. Replace every line with your own.
-->

## Header
Jordan Lee | 407-555-0142 | jordan.lee@example.com | [linkedin.com/in/jordan-lee-example](https://linkedin.com/in/jordan-lee-example) | [github.com/jordan-lee-example](https://github.com/jordan-lee-example)

## Education
### University of Central Florida | Orlando, FL
Bachelor of Science in Computer Science | GPA: 3.8 | May 2028

## Experience
### Software Engineering Intern | May 2026 -- Aug. 2026
Tidewater Freight | Orlando, FL
- Built a **Python** and **PostgreSQL** billing reconciliation service that matched every carrier invoice to its shipment and fuel records, cutting invoice mismatches by **40%** across **3 regional hubs** and **18,000+ monthly invoices**.
- Moved **12 nightly cron jobs** onto a **Redis** job queue with retries, removing **5 hours a week** of manual reruns.
- Blocked **30 failing deploys** before production with **GitHub Actions** CI checks running tests on each pull request.
<!-- alt -->
- Designed **REST APIs** for the billing service used by **3 internal teams**, with OpenAPI docs and versioning.
- Containerized the billing service with **Docker** and deployed it to **AWS ECS** behind an application load balancer.
<!-- /alt -->

### Undergraduate Research Assistant | Jan. 2026 -- Present
University of Central Florida | Orlando, FL
- Cut labeling time from **2 weeks to 3 days** for **20,000+ field images** with a **FastAPI** review tool that pre-sorts photos by model confidence, so the lab's annotators check the least certain photos first and skip the clear ones.
- Trained a **PyTorch** image classifier that flags invasive plants in drone photos, raising accuracy from **71% to 89%**.
- Sped up nightly model evaluation from **4 hours to 35 minutes** by batching inference on the lab's **NVIDIA** GPUs and caching image features between runs, so each model change gets scored before the next lab meeting.
<!-- alt -->
- Wrote **Pandas** and **NumPy** scripts that clean and split survey data by site, so test photos never leak into training.
<!-- /alt -->

### Web Developer | Aug. 2025 -- Dec. 2025
UCF Student Government | Orlando, FL
- Rebuilt the club funding portal in **React** and **TypeScript**, serving **600+ clubs** and **1,900+** yearly requests.
- Reduced page load time from **3.4s to 900ms** by moving reports to server-side pagination with cached **SQL** queries.
- Raised on-time funding requests by **25%** with automated deadline reminders sent from a scheduled **Node.js** worker that reads each club's open funding requests and emails the club treasurer three days before each funding cutoff.

## Projects
### [FloodWatch](https://github.com/jordan-lee-example/floodwatch) | Python, TypeScript, React, FastAPI, PostgreSQL, Mapbox
- Engineered a dashboard that ranks neighborhoods by flood risk, turning rain gauge and county drainage data into live street-level alerts, winning the **Best Civic Hack** of **180 projects** at Lakeside University's **LakeHacks**.
- Refreshed risk scores every **5 minutes** for **40,000+ addresses** with a **FastAPI** scoring service on **PostgreSQL**.
- Lowered map render time from **6s to 1.1s** by serving precomputed vector tiles to the **React** and Mapbox frontend.

### [Shuttle](https://github.com/jordan-lee-example/shuttle) | TypeScript, Next.js, Redis, Vercel, Playwright
- Launched a web app that shows live arrival times for campus shuttles, used by **1,200+ students** every week.
- Kept arrival estimates within **1 minute** by polling the GPS feed every **15 seconds** and caching it at the edge, then streaming updates to every open browser page over server-sent events instead of reloading the whole route schedule.
- Predicted arrivals from the route schedule when the GPS feed dropped, keeping it useful through **98%** of outages.

### [Ledgerline](https://github.com/jordan-lee-example/ledgerline) | Go, SQLite, Docker, GitHub Actions
- Wrote a command-line tool that turns bank CSV exports into monthly budget reports, installed by **300+ users**.
- Parsed statements from **9 bank formats** into one **SQLite** schema with a pluggable importer for each format.
- Published signed binaries for **macOS**, **Linux** and **Windows** in **8 minutes** from one **GitHub Actions** pipeline.

### [StudyBuddy](https://github.com/jordan-lee-example/studybuddy) | Swift, SwiftUI, Firebase
- Built an iOS app that turns a course syllabus into a study calendar with reminders, used by **400+ students**.
- Synced study plans across iPhone and iPad in under **2 seconds** with **Firebase** and offline-first local storage.
- Pulled due dates from **PDF** syllabi with on-device text recognition, filling in **90%** of calendars automatically.

<!-- alt -->
### [Quill](https://github.com/jordan-lee-example/quill) | Python, discord.py, PostgreSQL, Docker
- Built a Discord bot that runs office-hours queues for computer science courses, used by **900+ students**.
- Cut average wait for help from **25 to 9 minutes** by matching students to the TA who knows their topic.
<!-- /alt -->

## Technical Skills
- Languages: Python, TypeScript, JavaScript, Go, Java, C, SQL, Bash, HTML/CSS
- Frameworks: React, Next.js, Node.js, Express, FastAPI, Flask, Tailwind, Jest, Playwright, pytest
- Databases: PostgreSQL, MySQL, SQLite, Redis, MongoDB, Firebase
- AI/ML: PyTorch, scikit-learn, Pandas, NumPy, OpenCV, Jupyter
- Cloud: AWS, Docker, Linux, Git, CI/CD, Vercel, Nginx, Terraform, Grafana, Prometheus, GCP, Kafka, REST APIs
<!-- alt -->
- Concepts: distributed systems, data structures, algorithms, unit testing, code review
<!-- /alt -->

## Confirmed terms
<!-- When the agent asks "have you used X?" and you say yes, it records X here
     with one line of where you used it, so it never asks again. Never printed. -->
