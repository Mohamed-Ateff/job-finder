# Job Finder

Finds new jobs, scores them against a profile and writes a CV for each one.

Runs on Render's free plan. People, jobs and CVs are kept in a private Hugging Face dataset
(the server's own disk is wiped on every restart). The app visits its own address every
5 minutes so the free server never falls asleep.
