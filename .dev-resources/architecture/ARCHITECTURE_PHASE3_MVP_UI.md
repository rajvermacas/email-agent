# Info-Agent Phase 3: MVP UI Architecture

## Executive Summary

This document describes the **Minimum Viable Product (MVP) UI** for the Info-Agent system. Building on the complete backend from Phases 1 and 2, this phase adds a basic frontend for workflow management and email interaction.

### Phase 3 Goals

1. Create frontend templates with Tailwind CSS
2. Implement HTMX for dynamic updates
3. Build workflow creation and file upload views
4. Add basic workflow status viewing (polling-based)
5. Create Mock Email Server Web UI for demo
6. Enable plan approval via UI

### What This Phase Delivers

- A working web interface that can:
  - Create new workflows with name and description
  - Upload the 4 required input files
  - View workflow status and execution plan
  - Approve or reject execution plans
  - View email inboxes for any address
  - Compose and send replies (simulate target person)
  - Basic polling-based status updates

### Prerequisites

- Phase 1 and Phase 2 fully implemented and working
- All backend tests passing

### What This Phase Does NOT Include

- AG-UI real-time streaming (Phase 4)
- Real-time status updates via SSE (Phase 4)
- Detailed validation results view (Phase 4)
- Audit log viewer with filtering (Phase 4)
- Email thread visualization (Phase 4)
- Countdown timers (Phase 4)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BROWSER                                         │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         MVP Dashboard                                   │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐     │ │
│  │  │ Workflow List    │  │ Create Workflow  │  │ Workflow Status  │     │ │
│  │  │ (Home)           │  │ (File Upload)    │  │ (Polling)        │     │ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘     │ │
│  │                                                                         │ │
│  │  ┌──────────────────┐  ┌──────────────────┐                           │ │
│  │  │ Plan Approval    │  │ Email Inbox      │                           │ │
│  │  │ (Approve/Reject) │  │ (View/Reply)     │                           │ │
│  │  └──────────────────┘  └──────────────────┘                           │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                          HTMX (AJAX)│                                        │
│                                    ▼                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ HTTP
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FASTAPI GATEWAY (Port 8000)                        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                      TEMPLATE ROUTES (Jinja2)                           ││
│  │  GET  /                    → index.html (Dashboard)                     ││
│  │  GET  /workflows/new       → workflow/create.html                       ││
│  │  GET  /workflows/{id}      → workflow/detail.html                       ││
│  │  GET  /workflows/{id}/approve → workflow/approve.html                   ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                      API ROUTES (JSON)                                  ││
│  │  POST /api/workflows       → Create workflow                            ││
│  │  GET  /api/workflows       → List workflows                             ││
│  │  GET  /api/workflows/{id}  → Get workflow                               ││
│  │  POST /api/workflows/{id}/files → Upload files                          ││
│  │  POST /api/workflows/{id}/approve → Approve plan                        ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                      STATIC FILES                                       ││
│  │  /static/css/app.css                                                    ││
│  │  /static/js/app.js                                                      ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │
┌─────────────────────────────────────────────────────────────────────────────┐
│                       MOCK EMAIL SERVER (Port 8025)                          │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                      EMAIL WEB UI ROUTES                                ││
│  │  GET  /                    → email/inboxes.html (List inboxes)          ││
│  │  GET  /inbox/{email}       → email/inbox.html (View inbox)              ││
│  │  GET  /message/{id}        → email/message.html (View message)          ││
│  │  GET  /compose/{email}     → email/compose.html (Compose reply)         ││
│  │  POST /send                → Send email                                 ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

### URL Structure

| URL | Component | Description |
|-----|-----------|-------------|
| `http://localhost:8000/` | Gateway | Main dashboard |
| `http://localhost:8000/workflows/new` | Gateway | Create workflow |
| `http://localhost:8000/workflows/{id}` | Gateway | Workflow detail |
| `http://localhost:8025/` | Email Server | List inboxes |
| `http://localhost:8025/inbox/raj@gmail.com` | Email Server | raj's inbox |
| `http://localhost:8025/inbox/mrinal@gmail.com` | Email Server | mrinal's inbox |

---

## Technology Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Templating | Jinja2 | 3.x | Server-side HTML rendering |
| Styling | Tailwind CSS | 4.0+ | Utility-first CSS framework |
| Interactivity | HTMX | 1.9+ | AJAX without JavaScript |
| Icons | Heroicons | 2.x | SVG icon set |
| Forms | HTML5 | - | Native form handling |
| File Upload | HTMX + HTML5 | - | Multi-file upload |

### Why These Technologies?

1. **Jinja2**: FastAPI's native templating, server-side rendering for SEO and simplicity
2. **Tailwind CSS**: Rapid UI development with utility classes, no custom CSS needed
3. **HTMX**: Modern AJAX without complex JavaScript frameworks, progressive enhancement
4. **No JavaScript Framework**: Keeps MVP simple, reduces complexity

---

## Frontend Structure

### Directory Layout

```
frontend/
├── templates/
│   ├── base.html                    # Base layout with Tailwind
│   ├── index.html                   # Dashboard/home page
│   │
│   ├── workflow/
│   │   ├── create.html              # Create workflow form
│   │   ├── detail.html              # Workflow status/detail
│   │   ├── approve.html             # Plan approval view
│   │   └── list.html                # Workflow list partial (HTMX)
│   │
│   ├── email/
│   │   ├── inboxes.html             # List all inboxes
│   │   ├── inbox.html               # Single inbox view
│   │   ├── message.html             # Single message view
│   │   └── compose.html             # Compose/reply form
│   │
│   └── components/
│       ├── header.html              # Header partial
│       ├── sidebar.html             # Sidebar navigation
│       ├── status_badge.html        # Status indicator component
│       ├── file_upload.html         # File upload component
│       ├── plan_step.html           # Plan step component
│       ├── email_row.html           # Email list row
│       └── alert.html               # Alert/notification component
│
└── static/
    ├── css/
    │   └── app.css                  # Custom styles (minimal)
    │
    └── js/
        ├── app.js                   # Main application JS
        └── htmx-config.js           # HTMX configuration
```

---

## Template Specifications

### 1. Base Template (`base.html`)

```html
<!DOCTYPE html>
<html lang="en" class="h-full bg-gray-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Info-Agent{% endblock %}</title>

    <!-- Tailwind CSS (CDN for MVP, bundle in production) -->
    <script src="https://cdn.tailwindcss.com"></script>

    <!-- HTMX -->
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>

    <!-- Custom Tailwind Config -->
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        primary: {
                            50: '#eff6ff',
                            100: '#dbeafe',
                            200: '#bfdbfe',
                            300: '#93c5fd',
                            400: '#60a5fa',
                            500: '#3b82f6',
                            600: '#2563eb',
                            700: '#1d4ed8',
                            800: '#1e40af',
                            900: '#1e3a8a',
                        }
                    }
                }
            }
        }
    </script>

    <!-- Custom Styles -->
    <link rel="stylesheet" href="/static/css/app.css">

    {% block head %}{% endblock %}
</head>
<body class="h-full" hx-boost="true">
    <div class="min-h-full">
        <!-- Navigation -->
        {% include "components/header.html" %}

        <div class="flex">
            <!-- Sidebar -->
            {% include "components/sidebar.html" %}

            <!-- Main Content -->
            <main class="flex-1 p-6">
                <!-- Flash Messages -->
                <div id="alerts" class="mb-4">
                    {% with messages = get_flashed_messages(with_categories=true) %}
                        {% if messages %}
                            {% for category, message in messages %}
                                {% include "components/alert.html" %}
                            {% endfor %}
                        {% endif %}
                    {% endwith %}
                </div>

                {% block content %}{% endblock %}
            </main>
        </div>
    </div>

    <!-- HTMX Config -->
    <script src="/static/js/htmx-config.js"></script>

    <!-- App JS -->
    <script src="/static/js/app.js"></script>

    {% block scripts %}{% endblock %}
</body>
</html>
```

### 2. Header Component (`components/header.html`)

```html
<nav class="bg-white shadow-sm border-b border-gray-200">
    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div class="flex h-16 justify-between">
            <div class="flex">
                <!-- Logo -->
                <div class="flex flex-shrink-0 items-center">
                    <a href="/" class="text-xl font-bold text-primary-600">
                        Info-Agent
                    </a>
                </div>

                <!-- Navigation Links -->
                <div class="hidden sm:ml-6 sm:flex sm:space-x-8">
                    <a href="/"
                       class="{% if request.path == '/' %}border-primary-500 text-gray-900{% else %}border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700{% endif %} inline-flex items-center border-b-2 px-1 pt-1 text-sm font-medium">
                        Dashboard
                    </a>
                    <a href="/workflows/new"
                       class="{% if request.path == '/workflows/new' %}border-primary-500 text-gray-900{% else %}border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700{% endif %} inline-flex items-center border-b-2 px-1 pt-1 text-sm font-medium">
                        New Workflow
                    </a>
                </div>
            </div>

            <!-- Right side -->
            <div class="flex items-center">
                <span class="text-sm text-gray-500">
                    Phase 3: MVP UI
                </span>
            </div>
        </div>
    </div>
</nav>
```

### 3. Sidebar Component (`components/sidebar.html`)

```html
<aside class="w-64 bg-white shadow-sm min-h-screen border-r border-gray-200 hidden lg:block">
    <div class="p-4">
        <h2 class="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Workflows
        </h2>

        <nav class="mt-4 space-y-1">
            <a href="/"
               class="{% if request.path == '/' %}bg-primary-50 text-primary-700{% else %}text-gray-700 hover:bg-gray-50{% endif %} group flex items-center px-3 py-2 text-sm font-medium rounded-md">
                <!-- Heroicon: list-bullet -->
                <svg class="mr-3 h-5 w-5 {% if request.path == '/' %}text-primary-500{% else %}text-gray-400{% endif %}" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 12h.007v.008H3.75V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-.375 5.25h.007v.008H3.75v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
                </svg>
                All Workflows
            </a>

            <a href="/workflows/new"
               class="{% if request.path == '/workflows/new' %}bg-primary-50 text-primary-700{% else %}text-gray-700 hover:bg-gray-50{% endif %} group flex items-center px-3 py-2 text-sm font-medium rounded-md">
                <!-- Heroicon: plus -->
                <svg class="mr-3 h-5 w-5 {% if request.path == '/workflows/new' %}text-primary-500{% else %}text-gray-400{% endif %}" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
                New Workflow
            </a>
        </nav>

        <h2 class="mt-8 text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Email Inboxes
        </h2>

        <nav class="mt-4 space-y-1">
            <a href="http://localhost:8025/inbox/raj@gmail.com"
               target="_blank"
               class="text-gray-700 hover:bg-gray-50 group flex items-center px-3 py-2 text-sm font-medium rounded-md">
                <!-- Heroicon: envelope -->
                <svg class="mr-3 h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
                </svg>
                raj@gmail.com
                <span class="ml-auto text-xs text-gray-400">↗</span>
            </a>

            <a href="http://localhost:8025/inbox/mrinal@gmail.com"
               target="_blank"
               class="text-gray-700 hover:bg-gray-50 group flex items-center px-3 py-2 text-sm font-medium rounded-md">
                <svg class="mr-3 h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
                </svg>
                mrinal@gmail.com
                <span class="ml-auto text-xs text-gray-400">↗</span>
            </a>

            <a href="http://localhost:8025/inbox/vishal@gmail.com"
               target="_blank"
               class="text-gray-700 hover:bg-gray-50 group flex items-center px-3 py-2 text-sm font-medium rounded-md">
                <svg class="mr-3 h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
                </svg>
                vishal@gmail.com
                <span class="ml-auto text-xs text-gray-400">↗</span>
            </a>
        </nav>
    </div>
</aside>
```

### 4. Dashboard/Home (`index.html`)

```html
{% extends "base.html" %}

{% block title %}Dashboard - Info-Agent{% endblock %}

{% block content %}
<div class="space-y-6">
    <!-- Page Header -->
    <div class="sm:flex sm:items-center sm:justify-between">
        <div>
            <h1 class="text-2xl font-bold text-gray-900">Workflows</h1>
            <p class="mt-1 text-sm text-gray-500">
                Manage your information collection workflows
            </p>
        </div>
        <div class="mt-4 sm:mt-0">
            <a href="/workflows/new"
               class="inline-flex items-center rounded-md bg-primary-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600">
                <!-- Heroicon: plus -->
                <svg class="-ml-0.5 mr-1.5 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
                New Workflow
            </a>
        </div>
    </div>

    <!-- Workflow List -->
    <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg">
        <div id="workflow-list"
             hx-get="/api/workflows"
             hx-trigger="load, every 10s"
             hx-target="#workflow-list"
             hx-swap="innerHTML">
            <!-- Loading state -->
            <div class="p-6 text-center text-gray-500">
                <svg class="animate-spin h-8 w-8 mx-auto text-primary-600" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <p class="mt-2">Loading workflows...</p>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

### 5. Workflow List Partial (`workflow/list.html`)

```html
{% if workflows %}
<ul role="list" class="divide-y divide-gray-100">
    {% for workflow in workflows %}
    <li class="relative flex justify-between gap-x-6 px-4 py-5 hover:bg-gray-50 sm:px-6">
        <div class="flex min-w-0 gap-x-4">
            <!-- Status Icon -->
            <div class="flex-none">
                {% if workflow.status == 'completed' %}
                <div class="h-10 w-10 rounded-full bg-green-100 flex items-center justify-center">
                    <svg class="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                </div>
                {% elif workflow.status == 'failed' %}
                <div class="h-10 w-10 rounded-full bg-red-100 flex items-center justify-center">
                    <svg class="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </div>
                {% elif workflow.status == 'awaiting_approval' %}
                <div class="h-10 w-10 rounded-full bg-yellow-100 flex items-center justify-center">
                    <svg class="h-6 w-6 text-yellow-600" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                </div>
                {% elif workflow.status in ['executing', 'waiting_for_response', 'validating'] %}
                <div class="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
                    <svg class="h-6 w-6 text-blue-600 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                    </svg>
                </div>
                {% else %}
                <div class="h-10 w-10 rounded-full bg-gray-100 flex items-center justify-center">
                    <svg class="h-6 w-6 text-gray-600" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                    </svg>
                </div>
                {% endif %}
            </div>

            <div class="min-w-0 flex-auto">
                <p class="text-sm font-semibold leading-6 text-gray-900">
                    <a href="/workflows/{{ workflow.id }}" class="hover:underline">
                        {{ workflow.name }}
                    </a>
                </p>
                <p class="mt-1 flex text-xs leading-5 text-gray-500">
                    {{ workflow.description or 'No description' }}
                </p>
            </div>
        </div>

        <div class="flex shrink-0 items-center gap-x-4">
            <div class="hidden sm:flex sm:flex-col sm:items-end">
                <!-- Status Badge -->
                {% include "components/status_badge.html" %}

                <p class="mt-1 text-xs leading-5 text-gray-500">
                    Created {{ workflow.created_at | timeago }}
                </p>
            </div>

            <!-- Action Button -->
            {% if workflow.status == 'awaiting_approval' %}
            <a href="/workflows/{{ workflow.id }}/approve"
               class="rounded-md bg-yellow-50 px-2.5 py-1.5 text-xs font-semibold text-yellow-700 shadow-sm ring-1 ring-inset ring-yellow-600/20 hover:bg-yellow-100">
                Review Plan
            </a>
            {% else %}
            <a href="/workflows/{{ workflow.id }}"
               class="rounded-md bg-white px-2.5 py-1.5 text-xs font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50">
                View
            </a>
            {% endif %}

            <!-- Chevron -->
            <svg class="h-5 w-5 flex-none text-gray-400" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" />
            </svg>
        </div>
    </li>
    {% endfor %}
</ul>
{% else %}
<div class="p-12 text-center">
    <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
    <h3 class="mt-2 text-sm font-semibold text-gray-900">No workflows</h3>
    <p class="mt-1 text-sm text-gray-500">Get started by creating a new workflow.</p>
    <div class="mt-6">
        <a href="/workflows/new"
           class="inline-flex items-center rounded-md bg-primary-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-500">
            <svg class="-ml-0.5 mr-1.5 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            New Workflow
        </a>
    </div>
</div>
{% endif %}
```

### 6. Create Workflow (`workflow/create.html`)

```html
{% extends "base.html" %}

{% block title %}Create Workflow - Info-Agent{% endblock %}

{% block content %}
<div class="max-w-2xl mx-auto">
    <!-- Page Header -->
    <div class="mb-8">
        <h1 class="text-2xl font-bold text-gray-900">Create New Workflow</h1>
        <p class="mt-1 text-sm text-gray-500">
            Set up a new information collection workflow by providing details and uploading required files.
        </p>
    </div>

    <!-- Form -->
    <form hx-post="/api/workflows"
          hx-encoding="multipart/form-data"
          hx-target="#form-result"
          hx-swap="innerHTML"
          class="space-y-8">

        <!-- Basic Information -->
        <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Basic Information</h2>

            <div class="space-y-4">
                <!-- Workflow Name -->
                <div>
                    <label for="name" class="block text-sm font-medium leading-6 text-gray-900">
                        Workflow Name <span class="text-red-500">*</span>
                    </label>
                    <div class="mt-2">
                        <input type="text"
                               name="name"
                               id="name"
                               required
                               placeholder="e.g., Recipe Collection from Raj"
                               class="block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-primary-600 sm:text-sm sm:leading-6">
                    </div>
                </div>

                <!-- Description -->
                <div>
                    <label for="description" class="block text-sm font-medium leading-6 text-gray-900">
                        Description
                    </label>
                    <div class="mt-2">
                        <textarea name="description"
                                  id="description"
                                  rows="3"
                                  placeholder="Brief description of what this workflow will collect..."
                                  class="block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-primary-600 sm:text-sm sm:leading-6"></textarea>
                    </div>
                </div>
            </div>
        </div>

        <!-- Input Files -->
        <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Input Files</h2>
            <p class="text-sm text-gray-500 mb-6">
                Upload the required configuration files for this workflow.
            </p>

            <div class="space-y-6">
                <!-- Instructions File -->
                <div>
                    <label for="instructions" class="block text-sm font-medium leading-6 text-gray-900">
                        Instructions File <span class="text-red-500">*</span>
                    </label>
                    <p class="text-xs text-gray-500 mb-2">
                        Contains the main request instructions (who to contact, what to request)
                    </p>
                    <div class="mt-2">
                        <input type="file"
                               name="instructions"
                               id="instructions"
                               required
                               accept=".txt,.md"
                               class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100">
                    </div>
                </div>

                <!-- FAQ File -->
                <div>
                    <label for="faq" class="block text-sm font-medium leading-6 text-gray-900">
                        FAQ File <span class="text-red-500">*</span>
                    </label>
                    <p class="text-xs text-gray-500 mb-2">
                        Common questions and answers for automated clarification handling
                    </p>
                    <div class="mt-2">
                        <input type="file"
                               name="faq"
                               id="faq"
                               required
                               accept=".txt,.md"
                               class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100">
                    </div>
                </div>

                <!-- Escalation File -->
                <div>
                    <label for="escalation" class="block text-sm font-medium leading-6 text-gray-900">
                        Escalation Rules File <span class="text-red-500">*</span>
                    </label>
                    <p class="text-xs text-gray-500 mb-2">
                        Defines escalation contacts and timeout rules
                    </p>
                    <div class="mt-2">
                        <input type="file"
                               name="escalation"
                               id="escalation"
                               required
                               accept=".txt,.md"
                               class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100">
                    </div>
                </div>

                <!-- Validation File -->
                <div>
                    <label for="validation" class="block text-sm font-medium leading-6 text-gray-900">
                        Validation Criteria File <span class="text-red-500">*</span>
                    </label>
                    <p class="text-xs text-gray-500 mb-2">
                        Specifies how to validate received documents
                    </p>
                    <div class="mt-2">
                        <input type="file"
                               name="validation"
                               id="validation"
                               required
                               accept=".txt,.md"
                               class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100">
                    </div>
                </div>
            </div>
        </div>

        <!-- Form Result -->
        <div id="form-result"></div>

        <!-- Submit -->
        <div class="flex items-center justify-end gap-x-4">
            <a href="/" class="text-sm font-semibold text-gray-900">Cancel</a>
            <button type="submit"
                    class="rounded-md bg-primary-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600">
                Create Workflow
            </button>
        </div>
    </form>
</div>
{% endblock %}
```

### 7. Workflow Detail (`workflow/detail.html`)

```html
{% extends "base.html" %}

{% block title %}{{ workflow.name }} - Info-Agent{% endblock %}

{% block content %}
<div class="space-y-6">
    <!-- Page Header -->
    <div class="sm:flex sm:items-center sm:justify-between">
        <div>
            <div class="flex items-center gap-x-3">
                <h1 class="text-2xl font-bold text-gray-900">{{ workflow.name }}</h1>
                {% include "components/status_badge.html" %}
            </div>
            <p class="mt-1 text-sm text-gray-500">
                {{ workflow.description or 'No description' }}
            </p>
        </div>
        <div class="mt-4 sm:mt-0 flex gap-x-3">
            {% if workflow.status == 'awaiting_approval' %}
            <a href="/workflows/{{ workflow.id }}/approve"
               class="inline-flex items-center rounded-md bg-yellow-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-yellow-500">
                Review Plan
            </a>
            {% endif %}
        </div>
    </div>

    <!-- Status Card (Auto-refreshing) -->
    <div id="status-card"
         hx-get="/api/workflows/{{ workflow.id }}/status"
         hx-trigger="load, every 5s"
         hx-target="#status-card"
         hx-swap="innerHTML"
         class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg">
        <!-- Loading state -->
        <div class="p-6 text-center text-gray-500">
            <svg class="animate-spin h-6 w-6 mx-auto text-primary-600" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <p class="mt-2">Loading status...</p>
        </div>
    </div>

    <!-- Execution Plan -->
    {% if workflow.plan %}
    <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-6">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Execution Plan</h2>

        <ol class="relative border-l border-gray-200 ml-3">
            {% for step in workflow.plan %}
            <li class="mb-6 ml-6">
                <span class="absolute flex items-center justify-center w-8 h-8 rounded-full -left-4
                    {% if step.status == 'completed' %}bg-green-100 text-green-800
                    {% elif step.status == 'in_progress' %}bg-blue-100 text-blue-800
                    {% elif step.status == 'failed' %}bg-red-100 text-red-800
                    {% else %}bg-gray-100 text-gray-800{% endif %}">
                    {{ loop.index }}
                </span>
                <h3 class="font-medium text-gray-900">{{ step.action }}</h3>
                <p class="text-sm text-gray-500">{{ step.description }}</p>
            </li>
            {% endfor %}
        </ol>
    </div>
    {% endif %}

    <!-- Audit Log (Basic) -->
    <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-6">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Activity Log</h2>

        {% if workflow.audit_log %}
        <ul class="space-y-3">
            {% for entry in workflow.audit_log[-10:] | reverse %}
            <li class="flex gap-x-3 text-sm">
                <span class="text-gray-400 w-32 flex-shrink-0">
                    {{ entry.timestamp | format_time }}
                </span>
                <span class="font-medium text-gray-900">{{ entry.action }}</span>
                <span class="text-gray-500">{{ entry.details }}</span>
            </li>
            {% endfor %}
        </ul>
        {% else %}
        <p class="text-sm text-gray-500">No activity yet.</p>
        {% endif %}
    </div>
</div>
{% endblock %}
```

### 8. Plan Approval (`workflow/approve.html`)

```html
{% extends "base.html" %}

{% block title %}Approve Plan - {{ workflow.name }}{% endblock %}

{% block content %}
<div class="max-w-3xl mx-auto space-y-6">
    <!-- Page Header -->
    <div>
        <a href="/workflows/{{ workflow.id }}" class="text-sm text-gray-500 hover:text-gray-700">
            ← Back to workflow
        </a>
        <h1 class="mt-2 text-2xl font-bold text-gray-900">Review Execution Plan</h1>
        <p class="mt-1 text-sm text-gray-500">
            Review the generated plan before execution begins.
        </p>
    </div>

    <!-- Parsed Requirements -->
    <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-6">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Understood Requirements</h2>

        <dl class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
                <dt class="text-sm font-medium text-gray-500">Target Person</dt>
                <dd class="mt-1 text-sm text-gray-900">
                    {{ workflow.target_name or 'N/A' }}
                    {% if workflow.target_email %}
                    <span class="text-gray-500">({{ workflow.target_email }})</span>
                    {% endif %}
                </dd>
            </div>
            <div>
                <dt class="text-sm font-medium text-gray-500">Requested Information</dt>
                <dd class="mt-1 text-sm text-gray-900">{{ workflow.requested_info or 'N/A' }}</dd>
            </div>
        </dl>
    </div>

    <!-- Execution Plan -->
    <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-6">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Execution Plan</h2>

        <ol class="relative border-l border-gray-200 ml-3">
            {% for step in workflow.plan %}
            <li class="mb-6 ml-6">
                <span class="absolute flex items-center justify-center w-8 h-8 bg-primary-100 text-primary-800 rounded-full -left-4 text-sm font-medium">
                    {{ loop.index }}
                </span>
                <h3 class="font-medium text-gray-900">{{ step.action | title | replace('_', ' ') }}</h3>
                <p class="text-sm text-gray-500">{{ step.description }}</p>
            </li>
            {% endfor %}
        </ol>
    </div>

    <!-- Approval Actions -->
    <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
        <div class="flex">
            <div class="flex-shrink-0">
                <svg class="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
                </svg>
            </div>
            <div class="ml-3">
                <h3 class="text-sm font-medium text-yellow-800">
                    Approval Required
                </h3>
                <div class="mt-2 text-sm text-yellow-700">
                    <p>
                        Once approved, the workflow will begin executing and emails will be sent.
                        Please review the plan carefully before approving.
                    </p>
                </div>
            </div>
        </div>
    </div>

    <!-- Action Buttons -->
    <div class="flex items-center justify-end gap-x-4">
        <form hx-post="/api/workflows/{{ workflow.id }}/approve"
              hx-vals='{"approved": false}'
              hx-target="#result"
              hx-swap="innerHTML">
            <button type="submit"
                    class="rounded-md bg-white px-4 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50">
                Reject & Regenerate
            </button>
        </form>

        <form hx-post="/api/workflows/{{ workflow.id }}/approve"
              hx-vals='{"approved": true}'
              hx-target="#result"
              hx-swap="innerHTML">
            <button type="submit"
                    class="rounded-md bg-primary-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600">
                Approve & Execute
            </button>
        </form>
    </div>

    <div id="result"></div>
</div>
{% endblock %}
```

### 9. Status Badge Component (`components/status_badge.html`)

```html
{% set status_config = {
    'created': {'bg': 'bg-gray-100', 'text': 'text-gray-800', 'label': 'Created'},
    'planning': {'bg': 'bg-blue-100', 'text': 'text-blue-800', 'label': 'Planning'},
    'awaiting_approval': {'bg': 'bg-yellow-100', 'text': 'text-yellow-800', 'label': 'Awaiting Approval'},
    'executing': {'bg': 'bg-blue-100', 'text': 'text-blue-800', 'label': 'Executing'},
    'waiting_for_response': {'bg': 'bg-purple-100', 'text': 'text-purple-800', 'label': 'Waiting for Response'},
    'escalated': {'bg': 'bg-orange-100', 'text': 'text-orange-800', 'label': 'Escalated'},
    'validating': {'bg': 'bg-indigo-100', 'text': 'text-indigo-800', 'label': 'Validating'},
    'completed': {'bg': 'bg-green-100', 'text': 'text-green-800', 'label': 'Completed'},
    'failed': {'bg': 'bg-red-100', 'text': 'text-red-800', 'label': 'Failed'}
} %}

{% set config = status_config.get(workflow.status, status_config.created) %}

<span class="inline-flex items-center rounded-full {{ config.bg }} px-2.5 py-0.5 text-xs font-medium {{ config.text }}">
    {{ config.label }}
</span>
```

---

## Mock Email Server Web UI

### 10. Email Inboxes (`email/inboxes.html`)

```html
<!DOCTYPE html>
<html lang="en" class="h-full bg-gray-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Inboxes - Mock Email Server</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
</head>
<body class="h-full">
    <div class="min-h-full">
        <!-- Header -->
        <nav class="bg-white shadow-sm border-b border-gray-200">
            <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                <div class="flex h-16 justify-between items-center">
                    <div class="flex items-center">
                        <span class="text-xl font-bold text-gray-900">
                            Mock Email Server
                        </span>
                    </div>
                    <div class="text-sm text-gray-500">
                        Demo Email Interface
                    </div>
                </div>
            </div>
        </nav>

        <!-- Main Content -->
        <main class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
            <h1 class="text-2xl font-bold text-gray-900 mb-6">Email Inboxes</h1>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {% for inbox in inboxes %}
                <a href="/inbox/{{ inbox.email }}"
                   class="block bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-6 hover:shadow-md transition-shadow">
                    <div class="flex items-center">
                        <div class="flex-shrink-0">
                            <div class="h-12 w-12 rounded-full bg-primary-100 flex items-center justify-center">
                                <svg class="h-6 w-6 text-primary-600" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
                                </svg>
                            </div>
                        </div>
                        <div class="ml-4">
                            <h2 class="text-lg font-semibold text-gray-900">{{ inbox.email }}</h2>
                            <p class="text-sm text-gray-500">
                                {{ inbox.message_count }} message{% if inbox.message_count != 1 %}s{% endif %}
                                {% if inbox.unread_count > 0 %}
                                <span class="ml-2 inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800">
                                    {{ inbox.unread_count }} unread
                                </span>
                                {% endif %}
                            </p>
                        </div>
                    </div>
                </a>
                {% else %}
                <div class="col-span-full text-center py-12">
                    <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                    <h3 class="mt-2 text-sm font-semibold text-gray-900">No inboxes</h3>
                    <p class="mt-1 text-sm text-gray-500">No emails have been sent yet.</p>
                </div>
                {% endfor %}
            </div>
        </main>
    </div>
</body>
</html>
```

### 11. Single Inbox (`email/inbox.html`)

```html
<!DOCTYPE html>
<html lang="en" class="h-full bg-gray-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ email }} - Mock Email Server</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
</head>
<body class="h-full">
    <div class="min-h-full">
        <!-- Header -->
        <nav class="bg-white shadow-sm border-b border-gray-200">
            <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                <div class="flex h-16 justify-between items-center">
                    <div class="flex items-center gap-x-4">
                        <a href="/" class="text-gray-500 hover:text-gray-700">
                            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
                            </svg>
                        </a>
                        <span class="text-xl font-bold text-gray-900">
                            {{ email }}
                        </span>
                    </div>
                    <div class="flex items-center gap-x-4">
                        <a href="/compose/{{ email }}"
                           class="inline-flex items-center rounded-md bg-primary-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-500">
                            <svg class="-ml-0.5 mr-1.5 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
                            </svg>
                            Compose
                        </a>
                    </div>
                </div>
            </div>
        </nav>

        <!-- Main Content -->
        <main class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
            <div id="message-list"
                 hx-get="/inbox/{{ email }}/messages"
                 hx-trigger="load, every 5s"
                 hx-target="#message-list"
                 hx-swap="innerHTML"
                 class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg">
                <!-- Loading -->
                <div class="p-6 text-center text-gray-500">
                    <svg class="animate-spin h-6 w-6 mx-auto text-primary-600" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                    </svg>
                    <p class="mt-2">Loading messages...</p>
                </div>
            </div>
        </main>
    </div>
</body>
</html>
```

### 12. Message List Partial (`email/message_list.html`)

```html
{% if messages %}
<ul role="list" class="divide-y divide-gray-100">
    {% for message in messages %}
    <li class="relative px-4 py-5 hover:bg-gray-50 sm:px-6 {% if not message.read %}bg-blue-50{% endif %}">
        <div class="flex justify-between gap-x-6">
            <div class="flex min-w-0 gap-x-4">
                <div class="min-w-0 flex-auto">
                    <div class="flex items-center gap-x-2">
                        {% if not message.read %}
                        <span class="h-2 w-2 rounded-full bg-blue-600"></span>
                        {% endif %}
                        <p class="text-sm font-semibold leading-6 text-gray-900">
                            {{ message.from_address }}
                        </p>
                    </div>
                    <p class="mt-1 text-sm font-medium text-gray-900">
                        {{ message.subject }}
                    </p>
                    <p class="mt-1 text-sm text-gray-500 truncate">
                        {{ message.body_text[:100] }}{% if message.body_text|length > 100 %}...{% endif %}
                    </p>
                </div>
            </div>

            <div class="flex shrink-0 flex-col items-end">
                <p class="text-xs text-gray-500">
                    {{ message.received_at | format_time }}
                </p>
                {% if message.attachments %}
                <p class="mt-1 text-xs text-gray-500">
                    <svg class="inline h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13" />
                    </svg>
                    {{ message.attachments | length }} attachment{% if message.attachments|length != 1 %}s{% endif %}
                </p>
                {% endif %}

                <div class="mt-2 flex gap-x-2">
                    <a href="/message/{{ message.id }}"
                       class="text-xs text-primary-600 hover:text-primary-500">
                        View
                    </a>
                    <a href="/compose/{{ email }}?reply_to={{ message.id }}"
                       class="text-xs text-primary-600 hover:text-primary-500">
                        Reply
                    </a>
                </div>
            </div>
        </div>
    </li>
    {% endfor %}
</ul>
{% else %}
<div class="p-12 text-center">
    <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
    <h3 class="mt-2 text-sm font-semibold text-gray-900">No messages</h3>
    <p class="mt-1 text-sm text-gray-500">This inbox is empty.</p>
</div>
{% endif %}
```

### 13. Compose Email (`email/compose.html`)

```html
<!DOCTYPE html>
<html lang="en" class="h-full bg-gray-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Compose - Mock Email Server</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
</head>
<body class="h-full">
    <div class="min-h-full">
        <!-- Header -->
        <nav class="bg-white shadow-sm border-b border-gray-200">
            <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                <div class="flex h-16 justify-between items-center">
                    <div class="flex items-center gap-x-4">
                        <a href="/inbox/{{ from_email }}" class="text-gray-500 hover:text-gray-700">
                            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
                            </svg>
                        </a>
                        <span class="text-xl font-bold text-gray-900">
                            {% if reply_to %}Reply{% else %}Compose{% endif %}
                        </span>
                    </div>
                </div>
            </div>
        </nav>

        <!-- Main Content -->
        <main class="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8 py-8">
            <form hx-post="/send"
                  hx-encoding="multipart/form-data"
                  hx-target="#result"
                  hx-swap="innerHTML"
                  class="space-y-6">

                <input type="hidden" name="from_email" value="{{ from_email }}">
                {% if reply_to %}
                <input type="hidden" name="reply_to" value="{{ reply_to.id }}">
                <input type="hidden" name="thread_id" value="{{ reply_to.thread_id }}">
                {% endif %}

                <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-6 space-y-4">
                    <!-- From -->
                    <div>
                        <label class="block text-sm font-medium leading-6 text-gray-900">From</label>
                        <p class="mt-1 text-sm text-gray-900">{{ from_email }}</p>
                    </div>

                    <!-- To -->
                    <div>
                        <label for="to" class="block text-sm font-medium leading-6 text-gray-900">To</label>
                        <input type="email"
                               name="to"
                               id="to"
                               required
                               value="{{ reply_to.from_address if reply_to else '' }}"
                               class="mt-2 block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-primary-600 sm:text-sm sm:leading-6">
                    </div>

                    <!-- Subject -->
                    <div>
                        <label for="subject" class="block text-sm font-medium leading-6 text-gray-900">Subject</label>
                        <input type="text"
                               name="subject"
                               id="subject"
                               required
                               value="{% if reply_to %}Re: {{ reply_to.subject }}{% endif %}"
                               class="mt-2 block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-primary-600 sm:text-sm sm:leading-6">
                    </div>

                    <!-- Body -->
                    <div>
                        <label for="body" class="block text-sm font-medium leading-6 text-gray-900">Message</label>
                        <textarea name="body"
                                  id="body"
                                  rows="10"
                                  required
                                  class="mt-2 block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-primary-600 sm:text-sm sm:leading-6">{% if reply_to %}

---
On {{ reply_to.received_at | format_time }}, {{ reply_to.from_address }} wrote:

{{ reply_to.body_text }}{% endif %}</textarea>
                    </div>

                    <!-- Attachment -->
                    <div>
                        <label for="attachment" class="block text-sm font-medium leading-6 text-gray-900">Attachment</label>
                        <input type="file"
                               name="attachment"
                               id="attachment"
                               class="mt-2 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100">
                    </div>
                </div>

                <div id="result"></div>

                <div class="flex items-center justify-end gap-x-4">
                    <a href="/inbox/{{ from_email }}" class="text-sm font-semibold text-gray-900">Cancel</a>
                    <button type="submit"
                            class="rounded-md bg-primary-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600">
                        Send
                    </button>
                </div>
            </form>
        </main>
    </div>
</body>
</html>
```

---

## Backend Routes (FastAPI)

### Template Routes

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render dashboard page."""
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )

@router.get("/workflows/new", response_class=HTMLResponse)
async def create_workflow_page(request: Request):
    """Render create workflow page."""
    return templates.TemplateResponse(
        "workflow/create.html",
        {"request": request}
    )

@router.get("/workflows/{workflow_id}", response_class=HTMLResponse)
async def workflow_detail_page(request: Request, workflow_id: str):
    """Render workflow detail page."""
    workflow = await get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404)

    return templates.TemplateResponse(
        "workflow/detail.html",
        {"request": request, "workflow": workflow}
    )

@router.get("/workflows/{workflow_id}/approve", response_class=HTMLResponse)
async def workflow_approve_page(request: Request, workflow_id: str):
    """Render workflow approval page."""
    workflow = await get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404)

    if workflow.status != "awaiting_approval":
        return RedirectResponse(f"/workflows/{workflow_id}")

    return templates.TemplateResponse(
        "workflow/approve.html",
        {"request": request, "workflow": workflow}
    )
```

### HTMX Partial Routes

```python
@router.get("/api/workflows", response_class=HTMLResponse)
async def list_workflows_partial(request: Request):
    """Return workflow list partial for HTMX."""
    workflows = await get_all_workflows()

    # Check if request is from HTMX
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "workflow/list.html",
            {"request": request, "workflows": workflows}
        )
    else:
        # Return JSON for API calls
        return JSONResponse([w.dict() for w in workflows])

@router.get("/api/workflows/{workflow_id}/status", response_class=HTMLResponse)
async def workflow_status_partial(request: Request, workflow_id: str):
    """Return workflow status partial for HTMX polling."""
    workflow = await get_workflow(workflow_id)

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "workflow/status_card.html",
            {"request": request, "workflow": workflow}
        )
    else:
        return JSONResponse(workflow.dict())
```

### Static Files Configuration

```python
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
```

---

## JavaScript Files

### HTMX Configuration (`htmx-config.js`)

```javascript
// HTMX Configuration
document.body.addEventListener('htmx:configRequest', function(event) {
    // Add CSRF token if needed
    // event.detail.headers['X-CSRFToken'] = getCsrfToken();
});

// Handle errors
document.body.addEventListener('htmx:responseError', function(event) {
    console.error('HTMX Error:', event.detail);

    // Show error notification
    const alertsDiv = document.getElementById('alerts');
    if (alertsDiv) {
        alertsDiv.innerHTML = `
            <div class="rounded-md bg-red-50 p-4 mb-4">
                <div class="flex">
                    <div class="flex-shrink-0">
                        <svg class="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clip-rule="evenodd" />
                        </svg>
                    </div>
                    <div class="ml-3">
                        <p class="text-sm font-medium text-red-800">
                            An error occurred. Please try again.
                        </p>
                    </div>
                </div>
            </div>
        `;
    }
});

// Handle successful form submissions
document.body.addEventListener('htmx:afterSwap', function(event) {
    // Scroll to top on page change
    if (event.detail.target.id === 'main-content') {
        window.scrollTo(0, 0);
    }
});
```

### Main Application JS (`app.js`)

```javascript
// Main application JavaScript

// Auto-dismiss alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('[data-auto-dismiss]');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            alert.remove();
        }, 5000);
    });
});

// File upload preview
function handleFileSelect(input, previewId) {
    const preview = document.getElementById(previewId);
    if (!preview) return;

    if (input.files && input.files[0]) {
        const file = input.files[0];
        preview.textContent = `Selected: ${file.name} (${formatFileSize(file.size)})`;
        preview.classList.remove('hidden');
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Confirm dangerous actions
function confirmAction(message) {
    return confirm(message || 'Are you sure you want to proceed?');
}
```

### Custom Styles (`app.css`)

```css
/* Custom styles (minimal - most styling via Tailwind) */

/* Loading spinner animation */
@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}

.animate-spin {
    animation: spin 1s linear infinite;
}

/* HTMX loading indicator */
.htmx-request .htmx-indicator {
    display: inline-block;
}

.htmx-indicator {
    display: none;
}

/* File input styling */
input[type="file"]::file-selector-button {
    cursor: pointer;
}

/* Smooth transitions for HTMX swaps */
.htmx-swapping {
    opacity: 0;
    transition: opacity 200ms ease-out;
}

.htmx-settling {
    opacity: 1;
    transition: opacity 200ms ease-in;
}
```

---

## Jinja2 Filters

```python
from datetime import datetime
from jinja2 import Environment

def timeago(value):
    """Convert datetime to 'time ago' format."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)

    now = datetime.utcnow()
    diff = now - value

    seconds = diff.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"

def format_time(value):
    """Format datetime for display."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.strftime("%b %d, %Y %H:%M")

# Register filters
templates.env.filters["timeago"] = timeago
templates.env.filters["format_time"] = format_time
```

---

## Directory Structure (Phase 3 Additions)

```
info-agent/
├── src/info_agent/
│   ├── api/
│   │   └── routes/
│   │       ├── templates.py         # NEW: Template routes
│   │       └── ... (from Phase 1-2)
│   │
│   └── email/
│       └── web_ui.py                # NEW: Email server web routes
│
├── frontend/                        # NEW
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── workflow/
│   │   │   ├── create.html
│   │   │   ├── detail.html
│   │   │   ├── approve.html
│   │   │   ├── list.html
│   │   │   └── status_card.html
│   │   ├── email/
│   │   │   ├── inboxes.html
│   │   │   ├── inbox.html
│   │   │   ├── message.html
│   │   │   ├── message_list.html
│   │   │   └── compose.html
│   │   └── components/
│   │       ├── header.html
│   │       ├── sidebar.html
│   │       ├── status_badge.html
│   │       ├── file_upload.html
│   │       ├── plan_step.html
│   │       ├── email_row.html
│   │       └── alert.html
│   │
│   └── static/
│       ├── css/
│       │   └── app.css
│       └── js/
│           ├── app.js
│           └── htmx-config.js
│
├── tests/
│   └── e2e/
│       └── test_ui_workflow.py      # NEW: UI tests
│
└── ... (rest from Phase 1-2)
```

---

## Dependencies (Phase 3 Additions)

```toml
[project]
dependencies = [
    # ... (all from Phase 1-2)

    # Templating
    "jinja2>=3.1.0",

    # Static files
    "aiofiles>=23.0.0",
]
```

---

## Testing Strategy (Phase 3)

### UI Tests

```python
# tests/e2e/test_ui_workflow.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_dashboard_loads():
    """Test dashboard page loads."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert "Workflows" in response.text

@pytest.mark.asyncio
async def test_create_workflow_page():
    """Test create workflow page."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/workflows/new")
        assert response.status_code == 200
        assert "Create New Workflow" in response.text
        assert "Instructions File" in response.text

@pytest.mark.asyncio
async def test_workflow_creation_via_form():
    """Test workflow creation via form submission."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Submit form with files
        files = {
            "instructions": ("instructions.txt", b"Send email to test@example.com"),
            "faq": ("faq.txt", b"Q: Test?\nA: Yes"),
            "escalation": ("escalation.txt", b"Escalate to admin@example.com"),
            "validation": ("validation.txt", b"Validate Excel format")
        }
        data = {"name": "Test Workflow", "description": "Test"}

        response = await client.post(
            "/api/workflows",
            data=data,
            files=files
        )

        assert response.status_code in [200, 201, 302]
```

---

## Phase 3 Completion Criteria

- [ ] Dashboard page loading with workflow list
- [ ] Create workflow form working with file uploads
- [ ] Workflow detail page showing status
- [ ] Plan approval page working
- [ ] HTMX polling updating status every 5 seconds
- [ ] Mock Email Server Web UI listing inboxes
- [ ] Email inbox view showing messages
- [ ] Email compose/reply working
- [ ] Static files (CSS, JS) loading correctly
- [ ] All UI tests passing
- [ ] Three-tab demo setup working:
  - Tab 1: `http://localhost:8000/` (Dashboard)
  - Tab 2: `http://localhost:8025/inbox/raj@gmail.com`
  - Tab 3: `http://localhost:8025/inbox/mrinal@gmail.com`

---

## Next Phase Preview

**Phase 4: Full UI** will add:
- AG-UI real-time streaming via SSE
- Real-time status updates (no polling)
- Detailed validation results view
- Audit log viewer with filtering
- Email thread visualization
- Countdown timers for timeouts
- Agent activity log
- Plan iteration feedback UI

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-13 | Claude | Initial Phase 3 architecture document |
