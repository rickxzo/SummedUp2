from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from jose import jwt
import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()


from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

JWT_SECRET = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7
security = HTTPBearer()


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload.get("user_id")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")


def connect_db():
    return psycopg2.connect(
        host="ep-fragrant-hall-aolwpyqt-pooler.c-2.ap-southeast-1.aws.neon.tech",
        dbname="neondb",
        user="neondb_owner",
        password=os.getenv('NEONDB_PASS'),
        sslmode="require",
    )

conn = connect_db()
cur = conn.cursor()
cur.execute("SELECT * FROM Users")
res = cur.fetchall()
print(res)
conn.close()


app = FastAPI()

@app.get("/signup")
def signup(
    email: str, name: str, password: str, phone: str
):
    try:
        conn = connect_db()
        cur = conn.cursor()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    try:
        cur.execute("SELECT * FROM Users WHERE email = %s", (email,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Email already registered")
        cur.execute(
            "INSERT INTO Users (email, name, password, phone) VALUES (%s, %s, %s, %s) RETURNING id",
            (email, name, generate_password_hash(password), phone)
        )
        user_id = cur.fetchone()[0]
        conn.commit()

        jwt_token = create_access_token({"user_id": str(user_id)})
        return {"access_token": jwt_token, "token_type": "bearer"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/login")
def login(
    email: str, password: str
):
    try:
        conn = connect_db()
        cur = conn.cursor()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database connection error in Login")

    try:
        cur.execute("SELECT id, password FROM Users WHERE email = %s", (email,))
        user = cur.fetchone()
        if not user or not check_password_hash(user[1], password):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        jwt_token = create_access_token({"user_id": str(user[0])})
        return {"access_token": jwt_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while logging in")
    finally:
        conn.close()


@app.get("/profile")
def profile(current_user: str = Depends(get_current_user)):
    try:
        conn = connect_db()
        cur = conn.cursor()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database connection error in Profile")

    try:
        cur.execute("SELECT email, name, phone FROM Users WHERE id = %s", (current_user,))
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"email": user[0], "name": user[1], "phone": user[2]}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while fetching profile")
    finally:
        conn.close()


@app.get("/projects")
def get_projects(current_user: str = Depends(get_current_user)):
    try:
        conn = connect_db()
        cur = conn.cursor()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database connection error in Get Projects")

    try:
        cur.execute("SELECT id, name, description FROM Projects WHERE owner_id = %s", (current_user,))
        projects = cur.fetchall()
        return [{"id": project[0], "name": project[1], "description": project[2]} for project in projects]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while fetching projects")
    finally:
        conn.close()


@app.get("/project-stakeholders")
def get_project_stakeholders(project_id: str, current_user: str = Depends(get_current_user)):
    try:
        conn = connect_db()
        cur = conn.cursor()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database connection error in Get Project Stakeholders")

    try:
        cur.execute("SELECT id, name, email, phone FROM Stakeholders WHERE project_id = %s", (project_id,))
        stakeholders = cur.fetchall()
        return [{"id": stakeholder[0], "name": stakeholder[1], "email": stakeholder[2], "phone": stakeholder[3]} for stakeholder in stakeholders]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while fetching project stakeholders")
    finally:
        conn.close()


@app.get("/project-updates")
def get_project_updates(project_id: str, current_user: str = Depends(get_current_user)):
    try:
        conn = connect_db()
        cur = conn.cursor()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database connection error in Get Project Updates")

    try:
        cur.execute("SELECT title, description, published_at FROM Updates WHERE project_id = %s AND project_id IN (SELECT id FROM Projects WHERE owner_id = %s)", (project_id, current_user))
        updates = cur.fetchall()
        return [{"title": update[0], "description": update[1], "published_at": update[2]} for update in updates]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/update-statements")
def get_update_statements(update_id: str, current_user: str = Depends(get_current_user)):
    try:
        conn = connect_db()
        cur = conn.cursor()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database connection error in Get Update Statements")

    try:
        cur.execute("SELECT message, email FROM Statements WHERE update_id = %s", (update_id,))
        statements = cur.fetchall()
        return [{"message": statement[0], "email": statement[1]} for statement in statements]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while fetching update statements")
    finally:
        conn.close()

@app.get("/create-project")
def create_project(
    title: str, description: str, current_user: str = Depends(get_current_user)
):
    try:
        conn = connect_db()
        cur = conn.cursor()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database connection error in Create Project")

    try:
        cur.execute(
            "INSERT INTO Projects (owner_id, name, description) VALUES (%s, %s, %s) RETURNING id",
            (current_user, title, description)
        )
        project_id = cur.fetchone()[0]
        conn.commit()
        return {"project_id": project_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Error occurred while creating project")
    finally:
        conn.close()

@app.get("/add-stakeholder")
def add_stakeholder(
    project_id: str, email: str, phone: str, current_user: str = Depends(get_current_user)
):
    try:
        conn = connect_db()
        cur = conn.cursor()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database connection error in Add Stakeholder")

    try:
        cur.execute("INSERT INTO Stakeholders (project_id, email, phone) VALUES (%s, %s, %s)",
                    (project_id, email, phone))
        conn.commit()
        return {"message": "Stakeholder added successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Error occurred while adding stakeholder")
    finally:
        conn.close()

@app.get("/publish-update")
def publish_update(
    project_id: str,
    title: str,
    description: str,
    current_user: str = Depends(get_current_user)
):
    try:
        conn = connect_db()
        cur = conn.cursor()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database connection error in Publish Update")

    try:
        cur.execute(
            "INSERT INTO Updates (project_id, title, description) VALUES (%s, %s, %s)",
            (project_id, title, description)
        )
        conn.commit()
        return {"message": "Update published successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Error occurred while publishing update")
    finally:
        conn.close()


@app.get("/upload-statement")
def upload_statement(
    update_id: str,
    message: str,
    email: str
):
    try:
        conn = connect_db()
        cur = conn.cursor()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database connection error in Upload Statement")

    try:
        cur.execute(
            "INSERT INTO Statements (update_id, message, email) VALUES (%s, %s, %s)",
            (update_id, message, email)
        )
        conn.commit()
        return {"message": "Statement uploaded successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/analysis-report")
def analysis_report(update_id: str, current_user: str = Depends(get_current_user)):
    try:
        conn = connect_db()
        cur = conn.cursor()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database connection error in Analysis Report")

    try:
        cur.execute("SELECT message FROM Statements WHERE update_id = %s", (update_id,))
        statements = cur.fetchall()
        report = {
            "total_statements": len(statements),
            "positive_feedback": 67,
            "negative_feedback": 33,
            "overview": "Amay proshno kore neel dhrubotara",
            "key_insights": [
                "Stakeholders are generally positive about the project",
                "Some concerns about timeline and budget",
                "Overall sentiment is optimistic"
            ],
            "recommendations": [
                "Hail Abhilasha",
                "Fuck Avijeet",
                "Fuck Thamma (WITH DUE RESPECT)"
            ]
        }
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error occurred while generating analysis report")
