# Master resume template

<!--
How the master works

The master is one long file with everything you have done. It is never sent
anywhere. For each job, the agent copies it, keeps the entries and bullets
that fit that posting, and trims the rest to one page.

Rules
- Put every job, project, research role, club role and award here, even small ones.
- Under each entry, write the bullets you would normally use, then add
  alternates inside an alt block. Each alternate says the same work with a
  different emphasis (scale, a tool, a result, the user). More alternates give
  the tailoring step more truthful ways to match a posting.
- Every number must be one you can explain in an interview. The agent never
  adds a metric, tool or experience that is not in this file.
- The Skills bank lists every tool you have really used. Tailoring picks from it.
- Keep the first bullet of each project a plain statement of what it is:
  "A <thing> that <does what> for <whom>".
- The agent's checker (skills/tailor-resume/scripts/resume_check.py) reads this
  layout: `##` sections, `###` entries, `- ` bullets, and alternates between
  `<!-- alt -->` and `<!-- /alt -->`.
-->

## Header
Jane Doe | City, ST | jane@example.com | linkedin.com/in/example | github.com/example

## Education
### Example University, B.S. Computer Science (Aug 2024 to May 2028)
- Relevant coursework: Data Structures, Operating Systems, Databases

## Experience
### Example Corp, Software Engineer Intern (May 2026 to Aug 2026)
- Built a billing reconciliation service in Python and PostgreSQL that cut invoice mismatches by 40%
- Moved 12 nightly cron jobs onto a Redis queue, removing 5 hours a week of manual reruns
- Added CI checks in GitHub Actions that blocked 30 failing deploys before production
<!-- alt -->
- Designed REST APIs for the billing service used by 3 internal teams
- Wrote integration tests with pytest covering the reconciliation edge cases behind the 40% drop
- Containerized the service with Docker and deployed it to AWS ECS
<!-- /alt -->

## Projects
### Trailmap (github.com/example/trailmap)
- A hiking app that plans day routes from public trail data, used by 2,000 people in its first month
- Built the route search in TypeScript and React Native with an A* search over a trail graph
- Cached tiles on device so routes load offline in under 1 second
<!-- alt -->
- Shipped a Node.js backend on AWS Lambda that serves route queries for 2,000 users
- Modeled the trail network in PostgreSQL with PostGIS for distance queries
<!-- /alt -->

## Skills bank
<!-- Every tool you have really used. Tailored copies show 4 to 5 rows picked from here. -->
- Languages: Python, TypeScript, JavaScript, SQL, Java
- Frameworks: React, React Native, Node.js, FastAPI
- Data: PostgreSQL, Redis, PostGIS
- Cloud and tools: AWS (ECS, Lambda), Docker, GitHub Actions, Git, Linux
- Practices: REST APIs, CI/CD, unit testing, code review

## Confirmed terms
<!-- When the agent asks "have you used X?" and you say yes, it records X here
     with one line of where you used it, so it never asks again. -->
