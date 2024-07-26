import os
GOOGLE_CLIENT_ID=os.environ['GOOGLE_CLIENT_ID']
GOOGLE_PROJECT_ID=os.environ['GOOGLE_PROJECT_ID']
GOOGLE_AUTH_URI=os.environ['GOOGLE_AUTH_URI']
GOOGLE_TOKEN_URI=os.environ['GOOGLE_TOKEN_URI']
GOOGLE_AUTH_PROVIDER=os.environ['GOOGLE_AUTH_PROVIDER']
GOOGLE_CLIENT_SECRET=os.environ['GOOGLE_CLIENT_SECRET']
REDIRECT_URL=os.environ['REDIRECT_URL']
client_secret = {"web":
                 {"client_id":GOOGLE_CLIENT_ID,
                  "project_id":GOOGLE_PROJECT_ID,
                  "auth_uri":GOOGLE_AUTH_URI,
                  "token_uri":GOOGLE_TOKEN_URI,
                  "auth_provider_x509_cert_url":GOOGLE_AUTH_PROVIDER
                  ,"client_secret":GOOGLE_CLIENT_SECRET,
                  "redirect_uris":[REDIRECT_URL]
                  }
                }


initial_html = """
# John Doe
*Full Stack Developer*
[LinkedIn](https://www.linkedin.com/in/johndoe)
[GitHub](https://github.com/johndoe)
[Email](mailto:johndoe@example.com)
[Phone](tel:+1234567890)

---

## Education
**Bachelor of Science in Computer Science**  
University Name, Graduation Year

---

## Experience
**Full Stack Developer**  
Company Name, Start Date - Present  
- Developed web applications using HTML, CSS, and JavaScript
- Collaborated with team members on project planning and execution
- Implemented responsive designs for optimal viewing across devices

**Intern, Software Engineering**  
Company Name, Start Date - End Date  
- Assisted with debugging and testing of software applications
- Participated in code reviews and contributed to team discussions
- Gained experience with version control systems such as Git

---

## Projects
**Project Name**  
Description of the project.

**Project Name**  
Description of the project.

---

## Skills
- HTML/CSS
- JavaScript
- Git
- Responsive Web Design
- Problem Solving
- Team Collaboration

---

## Languages
- English (Native)
- Spanish (Fluent)

---

## Certifications
- Certification Name, Issuing Organization

---

## Interests
- Hiking
- Photography
- Cooking

---

*References available upon request*
"""
