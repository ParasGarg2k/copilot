# Mergington High School Activities

A FastAPI application for browsing extracurricular activities and managing
student registrations.

## Run locally

1. Create and activate a virtual environment.
2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Start the development server from the repository root:

   ```powershell
   python -m uvicorn src.app:app --reload
   ```

4. Open <http://localhost:8000> for the website or
   <http://localhost:8000/docs> for the API documentation.

The app uses MongoDB at `mongodb://localhost:27017/` when it is available. If
MongoDB is not running, it logs a warning and uses in-memory storage; data in
that mode resets when the server restarts.

## Teacher demo accounts

| Username | Password |
| --- | --- |
| `mrodriguez` | `art123` |
| `mchen` | `chess456` |
| `principal` | `admin789` |

These are sample credentials for local development only. Do not use them in a
deployed environment.

## Main API routes

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/activities` | List activities; accepts day and time filters |
| `GET` | `/activities/days` | List days with scheduled activities |
| `POST` | `/auth/login` | Authenticate a teacher |
| `GET` | `/auth/check-session` | Validate a saved teacher session |
| `POST` | `/activities/{activity_name}/signup` | Register a student (teacher required) |
| `POST` | `/activities/{activity_name}/unregister` | Remove a registration (teacher required) |
