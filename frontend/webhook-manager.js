// Webhook Management JavaScript for CV Review System
let currentPositions = [];

// Initialize the webhook management interface
document.addEventListener('DOMContentLoaded', function() {
    loadPositions();
    loadWebhookStatus();
    
    // Event listeners
    document.getElementById('refreshStatusBtn').addEventListener('click', loadWebhookStatus);
    document.getElementById('positionSelect').addEventListener('change', onPositionSelect);
    document.getElementById('setupWebhookBtn').addEventListener('click', setupWebhook);
});

// Load available positions from Google Drive
async function loadPositions() {
    const positionSelect = document.getElementById('positionSelect');
    
    try {
        positionSelect.innerHTML = '<option value="">Loading positions...</option>';
        positionSelect.disabled = true;
        
        const response = await fetch('http://localhost:8000/gdrive/folders');
        if (!response.ok) throw new Error('Failed to load positions');
        
        const folders = await response.json();
        
        if (!Array.isArray(folders) || folders.length === 0) {
            positionSelect.innerHTML = '<option value="">No positions found</option>';
            return;
        }
        
        // Sort folders alphabetically
        folders.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));
        
        positionSelect.innerHTML = [
            '<option value="">Select a position to monitor...</option>',
            ...folders.map(folder => 
                `<option value="${folder.id}" data-name="${folder.name}">${folder.name}</option>`
            )
        ].join('');
        
        positionSelect.disabled = false;
        currentPositions = folders;
        
    } catch (error) {
        console.error('Error loading positions:', error);
        positionSelect.innerHTML = '<option value="">Error loading positions</option>';
        showMessage('setupResult', 'Error loading positions: ' + error.message, 'error');
    }
}

// Handle position selection
async function onPositionSelect() {
    const positionSelect = document.getElementById('positionSelect');
    const cvFolderIdInput = document.getElementById('cvFolderId');
    const setupButton = document.getElementById('setupWebhookBtn');
    
    const selectedPositionId = positionSelect.value;
    
    if (!selectedPositionId) {
        cvFolderIdInput.value = '';
        setupButton.disabled = true;
        return;
    }
    
    try {
        // Find CV folder within this position
        const subfolders = await fetchSubfolders(selectedPositionId);
        const cvFolder = subfolders.find(folder => folder.name === 'cv_list');
        
        if (cvFolder) {
            cvFolderIdInput.value = cvFolder.id;
            setupButton.disabled = false;
        } else {
            cvFolderIdInput.value = 'CV folder not found';
            setupButton.disabled = true;
            showMessage('setupResult', 'No "cv_list" folder found in this position', 'warning');
        }
        
    } catch (error) {
        console.error('Error loading CV folder:', error);
        cvFolderIdInput.value = 'Error loading folder';
        setupButton.disabled = true;
        showMessage('setupResult', 'Error loading CV folder: ' + error.message, 'error');
    }
}

// Fetch subfolders of a position
async function fetchSubfolders(parentFolderId) {
    const response = await fetch(`http://localhost:8000/gdrive/folders?parent_id=${encodeURIComponent(parentFolderId)}`);
    if (!response.ok) throw new Error('Failed to load subfolders');
    return await response.json();
}

// Load current webhook status
async function loadWebhookStatus() {
    const statusContainer = document.getElementById('webhookStatus');
    
    try {
        statusContainer.innerHTML = `
            <div class="loading-container">
                <div class="spinner"></div>
                <div class="loading-text">Loading webhook status...</div>
            </div>
        `;
        
        const response = await fetch('http://localhost:8000/webhook/status');
        if (!response.ok) throw new Error('Failed to load webhook status');
        
        const status = await response.json();
        renderWebhookStatus(status);
        
    } catch (error) {
        console.error('Error loading webhook status:', error);
        statusContainer.innerHTML = `
            <div class="status-message status-error">
                <i class="fas fa-exclamation-circle"></i>
                Error loading webhook status: ${error.message}
            </div>
        `;
    }
}

// Render webhook status display
function renderWebhookStatus(status) {
    const statusContainer = document.getElementById('webhookStatus');
    const monitoredFolders = status.monitored_folders || {};
    const activeChannels = status.active_channels || [];
    
    if (Object.keys(monitoredFolders).length === 0) {
        statusContainer.innerHTML = `
            <div class="status-message status-info">
                <i class="fas fa-info-circle"></i>
                No positions are currently being monitored for automatic CV processing.
            </div>
        `;
        return;
    }
    
    let html = `
        <div class="status-summary">
            <div class="status-stat">
                <div class="stat-number">${Object.keys(monitoredFolders).length}</div>
                <div class="stat-label">Monitored Positions</div>
            </div>
            <div class="status-stat">
                <div class="stat-number">${activeChannels.length}</div>
                <div class="stat-label">Active Webhooks</div>
            </div>
        </div>
        
        <div class="monitored-positions">
            <h3><i class="fas fa-eye"></i> Currently Monitored Positions:</h3>
    `;
    
    for (const [folderId, positionName] of Object.entries(monitoredFolders)) {
        const correspondingChannel = activeChannels.find(channel => channel.includes(folderId));
        
        html += `
            <div class="monitored-position">
                <div class="position-info">
                    <div class="position-name">
                        <i class="fas fa-briefcase"></i>
                        ${positionName}
                    </div>
                    <div class="position-status">
                        <span class="status-badge status-active">
                            <i class="fas fa-check-circle"></i>
                            Active
                        </span>
                    </div>
                </div>
                <div class="position-actions">
                    <button class="btn btn-danger btn-small" onclick="stopMonitoring('${correspondingChannel || ''}', '${positionName}')">
                        <i class="fas fa-stop"></i>
                        Stop Monitoring
                    </button>
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    statusContainer.innerHTML = html;
}

// Setup webhook for selected position
async function setupWebhook() {
    const positionSelect = document.getElementById('positionSelect');
    const cvFolderId = document.getElementById('cvFolderId').value;
    const setupButton = document.getElementById('setupWebhookBtn');
    
    if (!positionSelect.value || !cvFolderId) {
        showMessage('setupResult', 'Please select a position first', 'warning');
        return;
    }
    
    const positionName = positionSelect.options[positionSelect.selectedIndex].dataset.name;
    
    try {
        setupButton.disabled = true;
        setupButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Setting up...';
        
        const response = await fetch('http://localhost:8000/webhook/setup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                folder_id: cvFolderId,
                position_name: positionName
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Setup failed');
        }
        
        const result = await response.json();
        
        showMessage('setupResult', 
            `✅ Auto-processing enabled for "${positionName}". CVs uploaded to this position will be automatically reviewed!`, 
            'success');
        
        // Refresh status and reset form
        await loadWebhookStatus();
        positionSelect.value = '';
        document.getElementById('cvFolderId').value = '';
        
    } catch (error) {
        console.error('Error setting up webhook:', error);
        showMessage('setupResult', 'Error setting up auto-processing: ' + error.message, 'error');
    } finally {
        setupButton.disabled = false;
        setupButton.innerHTML = '<i class="fas fa-rocket"></i> Enable Auto-Processing';
    }
}

// Stop monitoring a position
async function stopMonitoring(channelId, positionName) {
    if (!channelId) {
        showMessage('setupResult', 'Cannot stop monitoring: Channel ID not found', 'error');
        return;
    }
    
    if (!confirm(`Are you sure you want to stop auto-processing for "${positionName}"?`)) {
        return;
    }
    
    try {
        const response = await fetch('http://localhost:8000/webhook/stop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ channel_id: channelId })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Stop failed');
        }
        
        showMessage('setupResult', 
            `✅ Stopped auto-processing for "${positionName}"`, 
            'success');
        
        // Refresh status
        await loadWebhookStatus();
        
    } catch (error) {
        console.error('Error stopping webhook:', error);
        showMessage('setupResult', 'Error stopping auto-processing: ' + error.message, 'error');
    }
}

// Show status message
function showMessage(elementId, message, type) {
    const element = document.getElementById(elementId);
    element.className = `status-message status-${type}`;
    
    const icons = {
        success: 'fas fa-check-circle',
        error: 'fas fa-exclamation-circle',
        warning: 'fas fa-exclamation-triangle',
        info: 'fas fa-info-circle'
    };
    
    element.innerHTML = `
        <i class="${icons[type] || icons.info}"></i>
        ${message}
    `;
    element.style.display = 'block';
    
    // Auto-hide success messages after 5 seconds
    if (type === 'success') {
        setTimeout(() => {
            element.style.display = 'none';
        }, 5000);
    }
}
