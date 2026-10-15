import os

import frappe

no_cache = 1

def get_context(context):
    # 1. Get the Token
    csrf_token = frappe.sessions.get_csrf_token()
    
    # 2. Find the build file
    file_path = frappe.get_app_path("sales_pwa", "public", "frontend", "index.html")
    
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            # No ?v= cache-buster: Vite already hashes every file name, and a query on
            # the entry script makes lazy chunks (which import it without one) load a
            # second copy of the app that re-mounts over the first.
            content = f.read()

            # 3. INJECT THE TOKEN into the HTML
            # We add a small script that sets window.csrf_token
            csrf_script = f'<script>window.csrf_token = "{csrf_token}";</script>'
            
            # Insert it right before the closing head tag
            if "</head>" in content:
                content = content.replace("</head>", f"{csrf_script}</head>")
            else:
                # Fallback if no head tag (rare)
                content = csrf_script + content
                
            context.build_content = content
    else:
        context.build_content = "Build not found. Please run npm run build."
