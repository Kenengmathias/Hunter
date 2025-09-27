#!/bin/bash

# Create Hunter Templates and Static Files

echo "🎨 Creating Hunter templates and static files..."

# Create directories
mkdir -p templates static/css static/js static/images

# Create templates (already done above)
echo "✅ Templates created"

# Create a simple custom CSS file for any additional styling
cat << 'CSS_EOF' > static/css/hunter.css
/* Hunter Job Search - Additional Custom Styles */

.pulse-animation {
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.5; }
    100% { opacity: 1; }
}

.job-card-hover-effect {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.job-card-hover-effect:hover {
    transform: translateY(-4px) scale(1.02);
}

.source-badge-indeed { background: #2557a7; }
.source-badge-jobberman { background: #ff6b35; }
.source-badge-jsearch { background: #10b981; }
.source-badge-jooble { background: #8b5cf6; }
.source-badge-adzuna { background: #f59e0b; }

/* Mobile optimizations */
@media (max-width: 576px) {
    .search-container {
        padding: 1rem;
    }
    
    .job-card {
        margin-bottom: 1rem;
    }
    
    .job-title {
        font-size: 1rem;
    }
}
CSS_EOF

# Create a simple JavaScript file for additional functionality
cat << 'JS_EOF' > static/js/hunter.js
// Hunter Job Search - Custom JavaScript

document.addEventListener('DOMContentLoaded', function() {
    
    // Enhanced search form validation
    const searchForm = document.getElementById('search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            const jobTitle = document.getElementById('job_title').value.trim();
            if (jobTitle.length < 2) {
                e.preventDefault();
                alert('Please enter at least 2 characters for job title.');
                return false;
            }
        });
    }
    
    // Job card interactions
    const jobCards = document.querySelectorAll('.job-card');
    jobCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.classList.add('job-card-hover-effect');
        });
        
        card.addEventListener('mouseleave', function() {
            this.classList.remove('job-card-hover-effect');
        });
    });
    
    // Search tips toggle
    const searchTips = document.getElementById('search-tips');
    if (searchTips) {
        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'btn btn-sm btn-outline-info';
        toggleBtn.innerHTML = '<i class="fas fa-question-circle"></i> Search Tips';
        toggleBtn.onclick = function() {
            searchTips.style.display = searchTips.style.display === 'none' ? 'block' : 'none';
        };
        
        // Add to search container
        const searchContainer = document.querySelector('.search-container');
        if (searchContainer) {
            searchContainer.appendChild(toggleBtn);
        }
    }
    
    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl + K to focus search
        if (e.ctrlKey && e.key === 'k') {
            e.preventDefault();
            const jobTitleInput = document.getElementById('job_title');
            if (jobTitleInput) {
                jobTitleInput.focus();
            }
        }
    });
    
    console.log('🏹 Hunter Job Search initialized!');
});

// Job application tracking
function trackJobApplication(source, title, company) {
    console.log(`Job Application Tracked:`, {
        source: source,
        title: title,
        company: company,
        timestamp: new Date().toISOString()
    });
    
    // You can integrate with analytics services here
    // Example: Google Analytics, Mixpanel, etc.
}

// Search analytics
function trackSearch(query, location, results_count) {
    console.log(`Search Tracked:`, {
        query: query,
        location: location,
        results: results_count,
        timestamp: new Date().toISOString()
    });
}
JS_EOF

# Create a favicon placeholder
cat << 'SVG_EOF' > static/images/favicon.svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <circle cx="50" cy="50" r="45" fill="#2c3e50"/>
    <circle cx="50" cy="50" r="35" fill="none" stroke="#3498db" stroke-width="3"/>
    <circle cx="50" cy="50" r="25" fill="none" stroke="#f39c12" stroke-width="2"/>
    <circle cx="50" cy="50" r="15" fill="none" stroke="#e74c3c" stroke-width="2"/>
    <circle cx="50" cy="50" r="3" fill="#e74c3c"/>
    <line x1="50" y1="35" x2="50" y2="15" stroke="#e74c3c" stroke-width="2"/>
    <line x1="65" y1="50" x2="85" y2="50" stroke="#e74c3c" stroke-width="2"/>
    <line x1="50" y1="65" x2="50" y2="85" stroke="#e74c3c" stroke-width="2"/>
    <line x1="35" y1="50" x2="15" y2="50" stroke="#e74c3c" stroke-width="2"/>
</svg>
SVG_EOF

echo "📁 Directory structure:"
echo "templates/"
echo "├── base.html"
echo "└── index.html"
echo "static/"
echo "├── css/"
echo "│   └── hunter.css"
echo "├── js/"
echo "│   └── hunter.js"
echo "└── images/"
echo "    └── favicon.svg"

echo ""
echo "✅ Templates and static files created successfully!"
echo "🚀 Your Hunter Job Search Engine is ready!"

