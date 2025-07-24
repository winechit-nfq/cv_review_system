// filepath: /Users/nfqlocal/cv_review_system/frontend/main.js
let currentCVs = [];
let reviewAllAbortController = null;

// Load CVs from selected source
async function loadCVs() {
  const source = document.getElementById('source').value;
  const cvListContainer = document.getElementById('cvListContainer');
  const cvList = document.getElementById('cvList');

  // Show container and loading state
  cvListContainer.style.display = 'block';
  cvList.innerHTML = `
    <div class="loading-container">
      <div class="spinner"></div>
      <div class="loading-text">Loading CVs from ${source}...</div>
    </div>
  `;
// Scroll to bottom after loading starts
  window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
  // Hide other sections
  hideAllSections();

  try {
    const res = await fetch(`http://localhost:8000/cvs?source=${source}`);
    if (!res.ok) throw new Error('Failed to load CVs');

    const cvs = await res.json();
    currentCVs = cvs;

    const reviewAllBtn = document.getElementById('reviewAllBtn');
    if (cvs.length === 0) {
      cvList.innerHTML = `
        <div class="status-message status-warning">
          <i class="fas fa-exclamation-triangle"></i>
          No CVs found in the selected source.
        </div>
      `;
      reviewAllBtn.disabled = true;
      // Scroll to bottom after loading
      cvListContainer.scrollIntoView({ behavior: 'smooth', block: 'end' });
      return;
    } else {
      reviewAllBtn.disabled = false;
    }

    // Render CV grid (without buttons)
    let html = '';
    cvs.forEach((cv, index) => {
      const ownerName = extractOwnerName(cv.name, cv.path);

      html += `
        <div class="cv-item slide-in" style="animation-delay: ${index * 0.1}s">
          <div class="cv-name">
            <i class="fas fa-file-pdf"></i>
            ${cv.name}
          </div>
          <div class="cv-owner">
            <i class="fas fa-user"></i>
            ${ownerName}
          </div>
        </div>
      `;
    });

    cvList.innerHTML = html;

  } catch (error) {
    cvList.innerHTML = `
      <div class="status-message status-error">
        <i class="fas fa-exclamation-circle"></i>
        Error loading CVs: ${error.message}
      </div>
    `;
  }

  
}

// Extract owner name from CV filename or path
function extractOwnerName(filename, path) {
  let name = filename.replace(/\.(pdf|doc|docx|txt)$/i, '');
  name = name.replace(/_(cv|resume|curriculum)$/i, '');
  name = name.replace(/_/g, ' ');
  name = name.replace(/^(cv|resume|curriculum)[\s_-]*/i, '');
  name = name.replace(/[\s_-]*(cv|resume|curriculum)$/i, '');
  name = name.split(' ').map(word =>
    word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
  ).join(' ');
  return name || 'Unknown';
}

// Review individual CV
async function reviewCV(cv) {
  const jobDescription = document.getElementById('jobDescription').value;
  const reviewBox = document.getElementById('reviewBox');
  const reviewContent = document.getElementById('reviewContent');

  reviewBox.style.display = 'block';
  reviewBox.scrollIntoView({ behavior: 'smooth' });

  reviewContent.innerHTML = `
    <div class="loading-container">
      <div class="spinner"></div>
      <div class="loading-text">Analyzing CV: ${cv.name}...</div>
    </div>
  `;

  // Scroll to bottom after loading starts
  window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });

  try {
    const res = await fetch('http://localhost:8000/review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...cv,
        job_description: jobDescription
      })
    });

    if (!res.ok) throw new Error('Review failed');

    const result = await res.json();
    reviewContent.innerHTML = marked.parse(result.review);

  } catch (error) {
    reviewContent.innerHTML = `
      <div class="status-message status-error">
        <i class="fas fa-exclamation-circle"></i>
        Error reviewing CV: ${error.message}
      </div>
    `;
  }
}

// Preview CV content
async function previewCV(cv) {
  const previewBox = document.getElementById('previewBox');
  const previewTitle = document.getElementById('previewTitle');
  const previewContent = document.getElementById('previewContent');

  previewBox.style.display = 'block';
  previewTitle.textContent = `Preview: ${cv.name}`;
  previewContent.innerHTML = 'Loading...';

  previewBox.scrollIntoView({ behavior: 'smooth' });

  try {
    const res = await fetch(`http://localhost:8000/cv_content?source=${cv.source}&path=${encodeURIComponent(cv.path)}`);
    if (!res.ok) throw new Error('Failed to load CV content');

    const text = await res.text();
    previewContent.textContent = text;

  } catch (error) {
    previewContent.innerHTML = `Error loading preview: ${error.message}`;
  }
}

// Review all CVs
async function reviewAllCVs() {
  const source = document.getElementById('source').value;
  const jobDescription = document.getElementById('jobDescription').value;
  const allReviewsBox = document.getElementById('allReviewsBox');
  const reviewAllBtn = document.getElementById('reviewAllBtn');
  const stopBtn = document.getElementById('stopReviewAllBtn');

  if (!jobDescription.trim()) {
    document.getElementById('jobDescription').focus();
    document.getElementById('jobDescription').classList.add('shake');
    setTimeout(() => document.getElementById('jobDescription').classList.remove('shake'), 500);
    return;
  }

  allReviewsBox.style.display = 'block';
  allReviewsBox.innerHTML = `
    <div class="loading-container">
      <div class="spinner"></div>
      <div class="loading-text">AI is analyzing and ranking all CVs...</div>
    </div>
  `;

  reviewAllBtn.disabled = true;
  stopBtn.style.display = 'inline-flex';
  reviewAllAbortController = new AbortController();

  try {
    const res = await fetch(`http://localhost:8000/review_all?source=${source}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(jobDescription),
      signal: reviewAllAbortController.signal
    });

    if (!res.ok) throw new Error('Review failed');

    const results = await res.json();
    renderResults(results);

  } catch (error) {
    if (error.name === 'AbortError') {
      allReviewsBox.innerHTML = `
        <div class="status-message status-warning">
          <i class="fas fa-hand-paper"></i>
          Review process stopped by user.
        </div>
      `;
    } else {
      allReviewsBox.innerHTML = `
        <div class="status-message status-error">
          <i class="fas fa-exclamation-circle"></i>
          Error during review: ${error.message}
        </div>
      `;
    }
  } finally {
    reviewAllBtn.disabled = false;
    stopBtn.style.display = 'none';
  }

  document.getElementById('allReviewsBox').style.display = 'block';
  document.getElementById('allReviewsBox').scrollIntoView({ behavior: 'smooth', block: 'end' });
}

// Stop review all process
function stopReviewAllCVs() {
  if (reviewAllAbortController) {
    reviewAllAbortController.abort();
  }
}

// Render results table with action buttons
function renderResults(results) {
  const allReviewsBox = document.getElementById('allReviewsBox');

  if (!Array.isArray(results) || results.length === 0) {
    allReviewsBox.innerHTML = `
      <div class="status-message status-warning">
        <i class="fas fa-search"></i>
        No reviews found.
      </div>
    `;
    return;
  }

  const topScore = Math.max(...results.map(r => r.fit_score));
  const avgScore = Math.round(results.reduce((sum, r) => sum + r.fit_score, 0) / results.length);

  const html = `
    <div class="results-container fade-in">
      <div class="results-header">
        <h2 class="results-title">
          <i class="fas fa-trophy"></i>
          CV Rankings
        </h2>
        <div class="results-summary">
          <div class="summary-item">
            <i class="fas fa-users"></i>
            <span><strong>${results.length}</strong> CVs</span>
          </div>
          <div class="summary-item">
            <i class="fas fa-star"></i>
            <span>Top: <strong>${topScore}</strong></span>
          </div>
          <div class="summary-item">
            <i class="fas fa-chart-line"></i>
            <span>Avg: <strong>${avgScore}</strong></span>
          </div>
        </div>
      </div>
      <div class="table-wrapper">
        <table class="results-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>CV Details</th>
              <th>Fit Score</th>
              <th>Actions</th>
              <th>Review</th>
            </tr>
          </thead>
          <tbody>
            ${results.map((result, index) => {
              const ownerName = extractOwnerName(result.cv_name, result.cv_path || '');
              const cvData = findCVData(result.cv_name, result.cv_path);

              return `
                <tr>
                  <td class="rank-cell ${getRankClass(index + 1)}">
                    ${getRankIcon(index + 1)} ${index + 1}
                  </td>
                  <td class="cv-info-cell">
                    <div class="cv-name-cell" title="${result.cv_name}">
                      <i class="fas fa-file-pdf"></i>
                      ${result.cv_name}
                    </div>
                    <div class="cv-owner-cell">
                      <i class="fas fa-user"></i>
                      ${ownerName}
                    </div>
                  </td>
                  <td>
                    <span class="score-badge ${getScoreClass(result.fit_score)}">
                      ${result.fit_score}
                    </span>
                  </td>
                  <td class="actions-cell">
                    <div class="action-buttons">
                      <button onclick='previewCV(${JSON.stringify(cvData).replace(/'/g, "&#39;")})' class="btn btn-secondary btn-xs" title="Preview Content">
                        <i class="fas fa-eye"></i>
                        Preview
                      </button>
                    </div>
                  </td>
                  <td class="review-content">
                    ${marked.parse(result.review)}
                  </td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;

  allReviewsBox.innerHTML = html;
  allReviewsBox.scrollIntoView({ behavior: 'smooth' });
}

// Find CV data from currentCVs array
function findCVData(cvName, cvPath) {
  const found = currentCVs.find(cv =>
    cv.name === cvName ||
    cv.path === cvPath ||
    cv.name.includes(cvName) ||
    cvName.includes(cv.name)
  );

  if (found) {
    return found;
  }

  return {
    name: cvName,
    path: cvPath || cvName,
    source: document.getElementById('source').value
  };
}

// Helper functions
function getRankClass(rank) {
  if (rank === 1) return 'rank-1';
  if (rank === 2) return 'rank-2';
  if (rank === 3) return 'rank-3';
  return '';
}

function getRankIcon(rank) {
  if (rank === 1) return '<i class="fas fa-trophy"></i>';
  if (rank === 2) return '<i class="fas fa-medal"></i>';
  if (rank === 3) return '<i class="fas fa-award"></i>';
  return '<i class="fas fa-user"></i>';
}

function getScoreClass(score) {
  if (score >= 80) return 'score-excellent';
  if (score >= 65) return 'score-good';
  if (score >= 50) return 'score-fair';
  return 'score-poor';
}

function hideAllSections() {
  document.getElementById('reviewBox').style.display = 'none';
  document.getElementById('previewBox').style.display = 'none';
  document.getElementById('allReviewsBox').style.display = 'none';
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
  const formControls = document.querySelectorAll('.form-control');
  formControls.forEach(control => {
    control.addEventListener('focus', function() {
      this.parentElement.style.transform = 'translateY(-2px)';
    });
    control.addEventListener('blur', function() {
      this.parentElement.style.transform = 'translateY(0)';
    });
  });

  const jobDescTextarea = document.getElementById('jobDescription');
  let saveTimeout;
  jobDescTextarea.addEventListener('input', function() {
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => {
      console.log('Job description updated');
    }, 1000);
  });

  document.addEventListener('keydown', function(e) {
    if (e.ctrlKey || e.metaKey) {
      switch(e.key) {
        case 'l':
          e.preventDefault();
          loadCVs();
          break;
        case 'r':
          e.preventDefault();
          if (currentCVs.length > 0) {
            reviewAllCVs();
          }
          break;
      }
    }
  });

  const tooltips = {
    'source': 'Choose where your CV files are stored',
    'jobDescription': 'Provide detailed job requirements for accurate AI matching',
    'reviewAllBtn': 'Keyboard shortcut: Ctrl/Cmd + R',
    'loadCVs': 'Keyboard shortcut: Ctrl/Cmd + L'
  };

  Object.entries(tooltips).forEach(([id, text]) => {
    const element = document.getElementById(id);
    if (element) {
      element.title = text;
    }
  });
});

// Add progress indication for long operations
function showProgress(message, progress = 0) {
  return `
    <div class="loading-container">
      <div class="spinner"></div>
      <div class="loading-text">${message}</div>
      ${progress > 0 ? `
        <div style="width: 200px; background: var(--border); border-radius: 10px; height: 8px; margin-top: 1rem; overflow: hidden;">
          <div style="width: ${progress}%; height: 100%; background: var(--primary); transition: width 0.3s ease;"></div>
        </div>
      ` : ''}
    </div>
  `;
}

// Enhanced error handling
function handleError(error, context) {
  console.error(`Error in ${context}:`, error);
  return `
    <div class="status-message status-error">
      <i class="fas fa-exclamation-circle"></i>
      <div>
        <strong>Error in ${context}</strong><br>
        <small>${error.message}</small>
      </div>
    </div>
  `;
}

// Add smooth scrolling utility
function smoothScrollTo(element) {
  element.scrollIntoView({
    behavior: 'smooth',
    block: 'center'
  });
}

// Add animation utility
function animateElement(element, animationClass) {
  element.classList.add(animationClass);
  element.addEventListener('animationend', () => {
    element.classList.remove(animationClass);
  }, { once: true });
}

// Export functionality for results
function exportResults(results, format = 'json') {
  if (!results || results.length === 0) return;

  let content, filename, mimeType;

  switch (format) {
    case 'csv':
      content = convertToCSV(results);
      filename = 'cv_rankings.csv';
      mimeType = 'text/csv';
      break;
    case 'json':
    default:
      content = JSON.stringify(results, null, 2);
      filename = 'cv_rankings.json';
      mimeType = 'application/json';
      break;
  }

  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function convertToCSV(results) {
  const headers = ['Rank', 'CV Name', 'Owner', 'Fit Score', 'Review Summary'];
  const rows = results.map((result, index) => [
    index + 1,
    `"${result.cv_name}"`,
    `"${extractOwnerName(result.cv_name, result.cv_path || '')}"`,
    result.fit_score,
    `"${result.review.replace(/"/g, '""').substring(0, 200)}..."`
  ]);

  return [headers, ...rows].map(row => row.join(',')).join('\n');
}

document.getElementById('darkModeToggle').onclick = function() {
  document.body.classList.toggle('dark-mode');
  this.innerHTML = document.body.classList.contains('dark-mode')
    ? '<i class="fas fa-sun"></i>'
    : '<i class="fas fa-moon"></i>';
};