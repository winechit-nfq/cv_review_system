// filepath: /Users/nfqlocal/cv_review_system/frontend/main.js
let currentCVs = [];
let qualifiedFolderId = '';
let reviewAllAbortController = null;
let CV_LIST_FOLDER_NAME = 'cv_list';
let JOB_DESCRIPTIONS_FOLDER_NAME = 'job_description';
let QUALIFICATIONS_CV_LIST_FOLDER_NAME = 'qualified_cv_list';

// Load folders from Google Drive
async function loadGDriveFolders() {
  const folderSelect = document.getElementById('folderSelect');
  folderSelect.innerHTML = '<option value="">Loading folders...</option>';
  folderSelect.disabled = true;

  try {
    const folders = await fetchGDriveFolders();

    if (!Array.isArray(folders) || folders.length === 0) {
      folderSelect.innerHTML = '<option value="">No folders found</option>';
      folderSelect.disabled = true;
      return;
    }

    // Sort folders alphabetically, case-insensitive
    folders.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));

    folderSelect.innerHTML = [
      '<option value="">Select an open position...</option>',
      ...folders.map(folder =>
      `<option value="${folder.id}" title="${folder.name}">${folder.name}</option>`
      )
    ].join('');
    folderSelect.disabled = false;
    
    // Store folders globally for batch processing
    window.allFolders = folders;
  } catch (error) {
    folderSelect.innerHTML = '<option value="">Error loading folders</option>';
    folderSelect.disabled = true;
    folderSelectContainer.insertAdjacentHTML('beforeend', handleError(error, 'Google Drive Folders'));
  }
}

// Fetch folders from Google Drive API
async function fetchGDriveFolders(parentFolderId = '') {
  let url = 'http://localhost:8000/gdrive/folders';
  if (parentFolderId) {
    url += `?parent_id=${encodeURIComponent(parentFolderId)}`;
  }
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to load folders');
    return await res.json();
  } catch (error) {
    throw error;
  }
}

// Load CVs from Google Drive
async function loadCVs(folderId = '') {
  const cvListContainer = document.getElementById('cvListContainer');
  const cvList = document.getElementById('cvList');

  try {

    const url = `http://localhost:8000/cvs?source=gdrive${folderId ? `&folder_id=${folderId}` : ''}`;
    const res = await fetch(url);
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

// Review all CVs in all folders
async function reviewAllFolders() {
  const allReviewsBox = document.getElementById('allReviewsBox');
  const reviewAllBtn = document.getElementById('reviewAllBtn');
  const stopBtn = document.getElementById('stopReviewAllBtn');

  if (!window.allFolders || window.allFolders.length === 0) {
    allReviewsBox.innerHTML = `
      <div class="status-message status-warning">
        <i class="fas fa-exclamation-triangle"></i>
        No folders available. Please wait for folders to load.
      </div>
    `;
    allReviewsBox.style.display = 'block';
    return;
  }

  allReviewsBox.style.display = 'block';
  allReviewsBox.innerHTML = `
    <div class="loading-container">
      <div class="spinner"></div>
      <div class="loading-text">Starting folder-by-folder CV analysis...</div>
      <div class="progress-info">Processing 0 of ${window.allFolders.length} folders</div>
    </div>
  `;
  allReviewsBox.scrollIntoView({ behavior: 'smooth', block: 'start' });

  reviewAllBtn.disabled = true;
  stopBtn.style.display = 'inline-flex';
  reviewAllAbortController = new AbortController();

  let allResults = [];
  let processedFolders = 0;

  try {
    for (const folder of window.allFolders) {
      // Check if process was aborted
      if (reviewAllAbortController.signal.aborted) {
        throw new Error('Process aborted by user');
      }

      // Update progress
      allReviewsBox.innerHTML = `
        <div class="loading-container">
          <div class="spinner"></div>
          <div class="loading-text">Processing folder: ${folder.name}</div>
          <div class="progress-info">Processing ${processedFolders + 1} of ${window.allFolders.length} folders</div>
          <div class="folder-progress">
            <div style="width: 300px; background: var(--border); border-radius: 10px; height: 12px; margin-top: 1rem; overflow: hidden;">
              <div style="width: ${((processedFolders + 1) / window.allFolders.length) * 100}%; height: 100%; background: var(--primary); transition: width 0.3s ease;"></div>
            </div>
          </div>
        </div>
      `;

      try {
        // Load folder contents (job description and CVs)
        await loadFolderContents(folder.id);
        
        // Check if we have CVs to review
        if (currentCVs && currentCVs.length > 0) {
          // Get job description
          const jobDescription = document.getElementById('jobDescription').value;
          
          if (jobDescription.trim()) {
            // Review all CVs in this folder
            const res = await fetch(`http://localhost:8000/review_all`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ 
                job_description: jobDescription, 
                cvs: currentCVs, 
                qualified_folder_id: qualifiedFolderId 
              }),
              signal: reviewAllAbortController.signal
            });

            if (res.ok) {
              const folderResults = await res.json();
              // Add folder name to each result
              const resultsWithFolder = folderResults.map(result => ({
                ...result,
                folder_name: folder.name
              }));
              allResults.push(...resultsWithFolder);
            }
          }
        }
      } catch (folderError) {
        console.error(`Error processing folder ${folder.name}:`, folderError);
        // Continue with next folder
      }

      processedFolders++;
    }

    // Render all results
    if (allResults.length > 0) {
      renderFolderResults(allResults);
    } else {
      allReviewsBox.innerHTML = `
        <div class="status-message status-warning">
          <i class="fas fa-search"></i>
          No CVs found to review across all folders.
        </div>
      `;
    }

  } catch (error) {
    if (error.name === 'AbortError' || error.message.includes('aborted')) {
      allReviewsBox.innerHTML = `
        <div class="status-message status-warning">
          <i class="fas fa-hand-paper"></i>
          Folder processing stopped by user.
        </div>
      `;
    } else {
      allReviewsBox.innerHTML = `
        <div class="status-message status-error">
          <i class="fas fa-exclamation-circle"></i>
          Error during folder processing: ${error.message}
        </div>
      `;
    }
  } finally {
    reviewAllBtn.disabled = false;
    stopBtn.style.display = 'none';
  }
}

// Review all CVs
async function reviewAllCVs() {
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
  // Scroll to top of the review box
  allReviewsBox.scrollIntoView({ behavior: 'smooth', block: 'start' });

  reviewAllBtn.disabled = true;
  stopBtn.style.display = 'inline-flex';
  reviewAllAbortController = new AbortController();

  try {
    const res = await fetch(`http://localhost:8000/review_all`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_description: jobDescription, cvs: currentCVs, qualified_folder_id: qualifiedFolderId }),
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

// Render results from multiple folders
function renderFolderResults(results) {
  const allReviewsBox = document.getElementById('allReviewsBox');

  if (!Array.isArray(results) || results.length === 0) {
    allReviewsBox.innerHTML = `
      <div class="status-message status-warning">
        <i class="fas fa-search"></i>
        No reviews found across all folders.
      </div>
    `;
    return;
  }

  // Group results by folder/position
  const resultsByFolder = {};
  results.forEach(result => {
    const folderName = result.folder_name;
    if (!resultsByFolder[folderName]) {
      resultsByFolder[folderName] = [];
    }
    resultsByFolder[folderName].push(result);
  });

  // Sort results within each folder by fit_score descending
  Object.keys(resultsByFolder).forEach(folderName => {
    resultsByFolder[folderName].sort((a, b) => b.fit_score - a.fit_score);
  });

  const totalCVs = results.length;
  const totalFolders = Object.keys(resultsByFolder).length;
  const overallTopScore = Math.max(...results.map(r => r.fit_score));
  const overallAvgScore = Math.round(results.reduce((sum, r) => sum + r.fit_score, 0) / results.length);

  let html = `
    <div class="results-container fade-in">
      <div class="results-header">
        <h2 class="results-title">
          <i class="fas fa-trophy"></i>
          CV Rankings by Position
        </h2>
        <div class="results-summary">
          <div class="summary-item">
            <i class="fas fa-folder"></i>
            <span><strong>${totalFolders}</strong> Positions</span>
          </div>
          <div class="summary-item">
            <i class="fas fa-users"></i>
            <span><strong>${totalCVs}</strong> Total CVs</span>
          </div>
          <div class="summary-item">
            <i class="fas fa-star"></i>
            <span>Overall Top: <strong>${overallTopScore}</strong></span>
          </div>
          <div class="summary-item">
            <i class="fas fa-chart-line"></i>
            <span>Overall Avg: <strong>${overallAvgScore}</strong></span>
          </div>
          <div class="summary-item">
            <i class="fas fa-microchip"></i>
            <span>Total Tokens: <strong>${results.reduce((sum, r) => sum + r.total_tokens, 0).toLocaleString()}</strong></span>
          </div>
        </div>
      </div>
  `;

  // Generate a table for each position
  Object.entries(resultsByFolder).forEach(([folderName, folderResults]) => {
    const folderTopScore = Math.max(...folderResults.map(r => r.fit_score));
    const folderAvgScore = Math.round(folderResults.reduce((sum, r) => sum + r.fit_score, 0) / folderResults.length);
    const folderTotalTokens = folderResults.reduce((sum, r) => sum + r.total_tokens, 0);

    html += `
      <div class="position-section">
        <div class="position-header">
          <h3 class="position-title">
            <i class="fas fa-briefcase"></i>
            ${folderName}
          </h3>
          <div class="position-summary">
            <span class="position-stat">
              <i class="fas fa-users"></i>
              <strong>${folderResults.length}</strong> CVs
            </span>
            <span class="position-stat">
              <i class="fas fa-star"></i>
              Top: <strong>${folderTopScore}</strong>
            </span>
            <span class="position-stat">
              <i class="fas fa-chart-line"></i>
              Avg: <strong>${folderAvgScore}</strong>
            </span>
            <span class="position-stat">
              <i class="fas fa-microchip"></i>
              <strong>${folderTotalTokens.toLocaleString()}</strong> tokens
            </span>
          </div>
        </div>
        <div class="table-wrapper">
          <table class="results-table position-table">
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
              ${folderResults.map((result, index) => {
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
                      <div class="token-usage">
                        <small class="token-count" title="Total tokens">
                          <i class="fas fa-microchip"></i> ${result.total_tokens.toLocaleString()}
                        </small>
                      </div>
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
  });

  html += `</div>`;

  allReviewsBox.innerHTML = html;
  allReviewsBox.scrollIntoView({ behavior: 'smooth' });
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
          <div class="summary-item">
            <i class="fas fa-microchip"></i>
            <span>Total Tokens: <strong>${results.reduce((sum, r) => sum + r.total_tokens, 0).toLocaleString()}</strong></span>
          </div>
          <div class="summary-item">
            <i class="fas fa-arrow-right"></i>
            <span>Prompt: <strong>${results.reduce((sum, r) => sum + r.prompt_tokens, 0).toLocaleString()}</strong></span>
          </div>
          <div class="summary-item">
            <i class="fas fa-arrow-left"></i>
            <span>Completion: <strong>${results.reduce((sum, r) => sum + r.completion_tokens, 0).toLocaleString()}</strong></span>
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
                    <div class="token-usage">
                      <small class="token-count" title="Total tokens">
                        <i class="fas fa-microchip"></i> Total: ${result.total_tokens.toLocaleString()}
                      </small>
                      <small class="token-details">
                        <span title="Prompt tokens"><i class="fas fa-arrow-right"></i> ${result.prompt_tokens.toLocaleString()}</span>
                        <span title="Completion tokens"><i class="fas fa-arrow-left"></i> ${result.completion_tokens.toLocaleString()}</span>
                      </small>
                    </div>
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
    source: 'gdrive'
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

// Load both job description and CVs in parallel from a parent folder
async function loadFolderContents(parentFolderId) {
  try {
    // Fetch subfolders and load CVs & job description in parallel
    const folders = await fetchGDriveFolders(parentFolderId);

    // Find relevant subfolder IDs
    const cvFolderId = folders.find(folder => folder.name === CV_LIST_FOLDER_NAME)?.id || '';
    const jobDescFolderId = folders.find(folder => folder.name === JOB_DESCRIPTIONS_FOLDER_NAME)?.id || '';
    qualifiedFolderId = folders.find(folder => folder.name === QUALIFICATIONS_CV_LIST_FOLDER_NAME)?.id || '';
    
    // Load CVs and job description concurrently
    await Promise.all([
      loadJobDescription(jobDescFolderId),
      loadCVs(cvFolderId)
    ]);
  } catch (error) {
    console.error('Error loading folder contents:', error);
    document.getElementById('cvList').innerHTML = handleError(error, 'Folder Contents');
    throw error; // Re-throw to allow caller to handle if needed
  }
}

// Load job description from server based on selected folder
async function loadJobDescription(folderId = '') {
  const jobDescTextarea = document.getElementById('jobDescription');
  jobDescTextarea.value = 'Loading job description...';
  
  try {
    const url = `http://localhost:8000/job_description${folderId ? `?folder_id=${folderId}` : ''}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to load job description');
    const text = await res.text();
    jobDescTextarea.value = text;
  } catch (error) {
    jobDescTextarea.value = 'Error loading job description: ' + error.message;
  }
}

// Initialize
document.addEventListener('DOMContentLoaded', function () {
  // Hide folder selector since we're processing all folders
  const folderSelectContainer = document.getElementById('folderSelectContainer');
  if (folderSelectContainer) {
    folderSelectContainer.style.display = 'none';
  }

  // Hide CV list container initially
  const cvListContainer = document.getElementById('cvListContainer');
  if (cvListContainer) {
    cvListContainer.style.display = 'none';
  }

  // Hide job description container initially
  const jobDescContainer = document.getElementById('jobDescriptionContainer');
  if (jobDescContainer) {
    jobDescContainer.style.display = 'none';
  }

  // Update the Review All button to use the new function
  const reviewAllBtn = document.getElementById('reviewAllBtn');
  if (reviewAllBtn) {
    reviewAllBtn.textContent = 'Review & Rank All Positions';
    reviewAllBtn.onclick = reviewAllFolders;
  }

  // Initial load of folders
  loadGDriveFolders();

  const formControls = document.querySelectorAll('.form-control');
  formControls.forEach(control => {
    control.addEventListener('focus', function () {
      this.parentElement.style.transform = 'translateY(-2px)';
    });
    control.addEventListener('blur', function () {
      this.parentElement.style.transform = 'translateY(0)';
    });
  });

  const jobDescTextarea = document.getElementById('jobDescription');
  let saveTimeout;
  if (jobDescTextarea) {
    jobDescTextarea.addEventListener('input', function () {
      clearTimeout(saveTimeout);
      saveTimeout = setTimeout(() => {
        console.log('Job description updated');
      }, 1000);
    });
  }

  const tooltips = {
    'reviewAllBtn': 'Process all folders and rank CVs across all positions',
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

document.getElementById('darkModeToggle').onclick = function () {
  document.body.classList.toggle('dark-mode');
  this.innerHTML = document.body.classList.contains('dark-mode')
    ? '<i class="fas fa-sun"></i>'
    : '<i class="fas fa-moon"></i>';
};