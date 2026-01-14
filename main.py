from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error
from datetime import datetime

# Load environment variables
load_dotenv()

app = FastAPI(title="Portfolio API", version="2.0.0")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://localhost:3000",
        "https://portfolio-frontend-nithiyans-projects.vercel.app",
        "https://portfolio-frontend-orcin-sigma.vercel.app",
        "https://www.nithiyan.online"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
DB_CONFIG = {
    'host': os.getenv("DB_HOST", "localhost"),
    'user': os.getenv("DB_USER", "root"),
    'password': os.getenv("DB_PASSWORD", ""),
    'database': os.getenv("DB_NAME", "portfolio_db"),
    'port': int(os.getenv("DB_PORT", "3306")),
    'ssl_disabled': False,      
    'ssl_verify_cert': False,   
}

# Email configuration - SENDGRID
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

# Pydantic Models
class ContactMessage(BaseModel):
    name: str
    email: EmailStr
    message: str

class ContactResponse(BaseModel):
    success: bool
    message: str

class Profile(BaseModel):
    id: int
    name: str
    title: str
    bio: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    location: Optional[str]
    github_url: Optional[str]
    linkedin_url: Optional[str]
    twitter_url: Optional[str]
    profile_image: Optional[str]
    resume_url: Optional[str]

class Skill(BaseModel):
    id: int
    category: str
    name: str
    proficiency: int
    icon: Optional[str]

class Project(BaseModel):
    id: int
    title: str
    description: Optional[str]
    long_description: Optional[str]
    image_url: Optional[str]
    github_url: Optional[str]
    live_url: Optional[str]
    category: Optional[str]
    featured: bool
    technologies: List[str] = []

class Experience(BaseModel):
    id: int
    company: str
    position: str
    description: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    is_current: bool
    location: Optional[str]
    company_url: Optional[str]

# Database Connection Helper
def get_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

# Email Function - SENDGRID VERSION
def send_email(contact: ContactMessage):
    """Send email notification using SendGrid"""
    
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4;">
        <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
          <h2 style="color: #333; border-bottom: 2px solid #8b5cf6; padding-bottom: 10px;">New Contact Form Submission</h2>
          <div style="margin: 20px 0;">
            <p style="margin: 10px 0;"><strong style="color: #666;">Name:</strong> {contact.name}</p>
            <p style="margin: 10px 0;"><strong style="color: #666;">Email:</strong> {contact.email}</p>
          </div>
          <div style="margin: 20px 0;">
            <h3 style="color: #666; margin-bottom: 10px;">Message:</h3>
            <div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid #8b5cf6; border-radius: 4px;">
              <p style="margin: 0; line-height: 1.6; color: #333;">{contact.message}</p>
            </div>
          </div>
          <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #eee;">
            <p style="color: #999; font-size: 12px;">Reply to: {contact.email}</p>
          </div>
        </div>
      </body>
    </html>
    """
    
    message = Mail(
        from_email=SENDER_EMAIL,
        to_emails=RECEIVER_EMAIL,
        subject=f"Portfolio Contact: {contact.name}",
        html_content=html_content
    )
    
    # Set reply-to as the contact's email
    message.reply_to = contact.email
    
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        print(f"Email sent successfully! Status code: {response.status_code}")
        return True
    except Exception as e:
        print(f"Error sending email via SendGrid: {str(e)}")
        return False

# API Endpoints

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "Portfolio API v2.0 with MySQL is running"}

@app.get("/api/profile", response_model=Profile)
async def get_profile():
    """Get profile information"""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT * FROM profile LIMIT 1")
        profile = cursor.fetchone()
        
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        return profile
    finally:
        cursor.close()
        connection.close()

@app.get("/api/skills")
async def get_skills():
    """Get all skills grouped by category"""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT category, name, proficiency, icon 
            FROM skills 
            ORDER BY category, display_order
        """)
        skills = cursor.fetchall()
        
        # Group by category
        grouped = {}
        for skill in skills:
            category = skill['category']
            if category not in grouped:
                grouped[category] = []
            grouped[category].append({
                'name': skill['name'],
                'proficiency': skill['proficiency'],
                'icon': skill['icon']
            })
        
        # Format for frontend
        result = [
            {'category': category, 'items': [s['name'] for s in items]}
            for category, items in grouped.items()
        ]
        
        return result
    finally:
        cursor.close()
        connection.close()

@app.get("/api/projects")
async def get_projects(category: Optional[str] = None, featured: Optional[bool] = None):
    """Get all projects with optional filtering"""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        query = """
            SELECT p.*, GROUP_CONCAT(pt.technology) as technologies
            FROM projects p
            LEFT JOIN project_technologies pt ON p.id = pt.project_id
        """
        
        conditions = []
        params = []
        
        if category:
            conditions.append("p.category = %s")
            params.append(category)
        
        if featured is not None:
            conditions.append("p.featured = %s")
            params.append(featured)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " GROUP BY p.id ORDER BY p.display_order, p.created_at DESC"
        
        cursor.execute(query, params)
        projects = cursor.fetchall()
        
        # Format technologies as list
        for project in projects:
            if project['technologies']:
                project['technologies'] = project['technologies'].split(',')
            else:
                project['technologies'] = []
        
        return projects
    finally:
        cursor.close()
        connection.close()

@app.get("/api/projects/{project_id}")
async def get_project(project_id: int):
    """Get single project details"""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT p.*, GROUP_CONCAT(pt.technology) as technologies
            FROM projects p
            LEFT JOIN project_technologies pt ON p.id = pt.project_id
            WHERE p.id = %s
            GROUP BY p.id
        """, (project_id,))
        
        project = cursor.fetchone()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        if project['technologies']:
            project['technologies'] = project['technologies'].split(',')
        else:
            project['technologies'] = []
        
        return project
    finally:
        cursor.close()
        connection.close()

@app.get("/api/experience")
async def get_experience():
    """Get work experience"""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM experience 
            ORDER BY is_current DESC, start_date DESC
        """)
        experience = cursor.fetchall()
        return experience
    finally:
        cursor.close()
        connection.close()

@app.post("/api/contact", response_model=ContactResponse)
async def contact(contact_data: ContactMessage):
    """Handle contact form submissions"""
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        # Save to database
        cursor.execute("""
            INSERT INTO contact_messages (name, email, message)
            VALUES (%s, %s, %s)
        """, (contact_data.name, contact_data.email, contact_data.message))
        connection.commit()
        
        # Send email if configured
        email_sent = False
        if all([SENDGRID_API_KEY, SENDER_EMAIL, RECEIVER_EMAIL]):
            email_sent = send_email(contact_data)
            if not email_sent:
                print("Warning: Email sending failed, but message was saved to database")
        
        return ContactResponse(
            success=True,
            message="Your message has been sent successfully! I'll get back to you soon."
        )
    except Exception as e:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save message: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@app.get("/api/stats")
async def get_stats():
    """Get portfolio statistics"""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        stats = {}
        
        # Count projects
        cursor.execute("SELECT COUNT(*) as count FROM projects")
        stats['projects'] = cursor.fetchone()['count']
        
        # Count skills
        cursor.execute("SELECT COUNT(*) as count FROM skills")
        stats['skills'] = cursor.fetchone()['count']
        
        # Count messages
        cursor.execute("SELECT COUNT(*) as count FROM contact_messages")
        stats['messages'] = cursor.fetchone()['count']
        
        return stats
    finally:
        cursor.close()
        connection.close()

@app.get("/api/health")
async def health_check():
    """Detailed health check"""
    db_connected = False
    try:
        connection = get_db_connection()
        connection.close()
        db_connected = True
    except:
        pass
    
    return {
        "status": "healthy",
        "database_connected": db_connected,
        "email_configured": all([SENDGRID_API_KEY, SENDER_EMAIL, RECEIVER_EMAIL]),
        "version": "2.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
