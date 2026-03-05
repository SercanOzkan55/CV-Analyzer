CV Analyzer - Frontend (React + Vite)

Quick start (5 minutes):

1. Create project (or use this folder):

```bash
# from workspace root
cd frontend
npm install
npm run dev
```

2. The app talks to your backend at `/api/v1/...`. You can set a different backend host by creating a `.env` file at `frontend/.env` with:

```
VITE_API_BASE=https://your-backend.example.com
```

3. API usage:
- Analyze: `POST /api/v1/analyze-pdf` (form-data: `file`, `job_description`).
- Recruiter lists: `GET /api/v1/recruiter/candidates`, `GET /api/v1/recruiter/top_candidates`.
- Add header: `Authorization: Bearer TOKEN` (enter token in UI API Token field).

Deploy:
- Frontend: Deploy `frontend` to Vercel (build: `npm run build`).
- Backend: Deploy to Render / Railway and set `VITE_API_BASE` in Vercel environment variables to your backend URL.

Result preview (UI behavior):
- Upload a PDF, paste job description, click Analyze.
- Result shows `score` and `matched_skills` returned by backend.
- Recruiter Dashboard shows lists from recruiter endpoints.

Files added:
- `src/App.jsx`, `src/main.jsx`, `src/components/UploadForm.jsx`, `src/components/Dashboard.jsx`, `src/api.js`, `index.html`, `package.json`, `style.css`.

That's all — want me to run tests, commit these files, or create a Vercel deployment config? 
