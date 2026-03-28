-- Jobber Database Schema

CREATE TABLE IF NOT EXISTS profile (
    id SERIAL PRIMARY KEY,
    resume_md TEXT,
    skills TEXT[] DEFAULT '{}',
    target_roles TEXT[] DEFAULT ARRAY['Software Developer', 'Software Engineer', 'Full Stack Developer', 'Full Stack Engineer'],
    target_locations TEXT[] DEFAULT ARRAY['Vancouver, BC', 'Vancouver, British Columbia'],
    experience_years INTEGER,
    notes TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default profile seeded with Leon's resume
INSERT INTO profile (id, experience_years, resume_md) VALUES (1, 4, $$
# Leon Menzies — Software Engineer | Vancouver, BC

## Technical Skills
- **Programming & Backend:** PHP, Python, Node.js, Java, C++, MySQL, PostgreSQL
- **Cloud & DevOps:** AWS (S3, EC2, CloudFront, SQS), Docker, Nginx, CI/CD (GitHub Actions, CircleCI, Bitbucket Pipelines)
- **Testing & Quality:** Postman, Unit Testing, Regression Testing, SonarQube
- **Frontend & Frameworks:** React, React Native, TypeScript, HTML/CSS, Ruby on Rails, Laravel, Express.js, Flask
- **Core Strengths:** System design, secure API development, algorithms, rapid adaptation to new technologies

## Work Experience

### Software Engineer — VoPay International Inc. (June 2023 – Present) | Vancouver, BC
- Developed and maintained a high-performance, API-driven payment infrastructure using PHP, MySQL, and AWS
- Architected scalable, resilient cloud systems using AWS S3, EC2, CloudFront, and SQS
- Implemented static code analysis with SonarQube integrated into Bitbucket pipelines
- Built secure data management solutions compliant with PCI DSS and SOC 2
- Designed and tested APIs with Postman; automated regression and unit testing
- Leveraged AI-assisted development tools (Claude Code, GitHub Copilot) to accelerate delivery

### Full Stack Developer — New Zealand Exchange (Feb 2022 – Mar 2023) | Wellington, NZ
- Transformed Ruby on Rails monoliths into standalone REST APIs with JWT authentication
- Built an Express/Node.js performance-monitoring dashboard API using concurrent HTTP requests
- Engineered responsive React frontends; implemented data-manipulation algorithms in Ruby and JS
- Managed UAT, DR, and production deployments via CircleCI and GitHub Actions

### Tester Intern — New Zealand Exchange (Nov 2021 – Feb 2022) | Wellington, NZ
- Performed regression, integration, automation, and manual testing across multiple systems

## Education
**BSc Computer Science** — Victoria University of Wellington (Nov 2022)
Dean's List every year | GPA: 3.86/4
Coursework: Algorithms & Data Structures, System Design, Databases, Cybersecurity, Machine Learning, Concurrent Programming, Cloud & Networking

## Projects
**Macro Dash** — Full-stack economic dashboard; Python Flask API + MySQL backend, React/TypeScript frontend, deployed on Linode with Nginx/Gunicorn and CI/CD pipelines
**Fitness App** — Cross-platform React Native/Expo app with Flask backend, JWT + Sign In with Apple, AI-generated workout plans, Recoil state management
$$) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,

    -- Source
    source VARCHAR(60) NOT NULL,
    url TEXT NOT NULL,
    url_fingerprint VARCHAR(64) UNIQUE NOT NULL,
    title_company_fp VARCHAR(64),

    -- Job info
    title VARCHAR(500) NOT NULL,
    company VARCHAR(255) NOT NULL,
    location VARCHAR(255),
    is_remote BOOLEAN DEFAULT FALSE,
    is_hybrid BOOLEAN DEFAULT FALSE,
    job_type VARCHAR(50),
    salary_min INTEGER,
    salary_max INTEGER,
    salary_currency VARCHAR(10),

    -- Content
    description_raw TEXT,

    -- Dates
    posted_at TIMESTAMP WITH TIME ZONE,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- AI Ranking
    rank_score INTEGER CHECK (rank_score BETWEEN 0 AND 100),
    rank_summary TEXT,
    rank_match_reasons TEXT[] DEFAULT '{}',
    rank_concerns TEXT[] DEFAULT '{}',
    ranked_at TIMESTAMP WITH TIME ZONE,

    -- User actions
    status VARCHAR(20) DEFAULT 'new' CHECK (status IN ('new','saved','applied','rejected','archived')),
    user_notes TEXT,
    applied_at TIMESTAMP WITH TIME ZONE,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_rank_score ON jobs(rank_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_jobs_scraped_at ON jobs(scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_posted_at ON jobs(posted_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_jobs_title_company_fp ON jobs(title_company_fp);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id SERIAL PRIMARY KEY,
    source VARCHAR(60),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    finished_at TIMESTAMP WITH TIME ZONE,
    jobs_found INTEGER DEFAULT 0,
    jobs_new INTEGER DEFAULT 0,
    jobs_updated INTEGER DEFAULT 0,
    error_message TEXT,
    status VARCHAR(20) DEFAULT 'running' CHECK (status IN ('running','completed','failed'))
);

CREATE TABLE IF NOT EXISTS company_watchlist (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    ats_type VARCHAR(30) NOT NULL CHECK (ats_type IN ('greenhouse','lever','ashby','workday','other')),
    ats_slug VARCHAR(255) NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Auto-update updated_at on jobs
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS jobs_updated_at ON jobs;
CREATE TRIGGER jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
