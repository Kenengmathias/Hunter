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
