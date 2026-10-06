const API_BASE = 'http://localhost:8000/api/v1';
const HEADERS = {
    'Authorization': 'Bearer test-token'
};

let currentInspectionId = null;

// UI Elements
const statusText = document.getElementById('status-text');
const btnCreate = document.getElementById('btn-create');
const metaInspectionId = document.getElementById('meta-inspection-id');

const step2 = document.getElementById('step-2');
const fileUpload = document.getElementById('file-upload');
const btnUpload = document.getElementById('btn-upload');
const metaImageId = document.getElementById('meta-image-id');

const step3 = document.getElementById('step-3');
const btnRun = document.getElementById('btn-run');

const step4 = document.getElementById('step-4');
const btnResults = document.getElementById('btn-results');
const resultsContent = document.getElementById('results-content');

// 1. Create Inspection
btnCreate.addEventListener('click', async () => {
    try {
        btnCreate.disabled = true;
        btnCreate.textContent = 'Creating...';
        statusText.textContent = 'Creating inspection...';

        const response = await fetch(`${API_BASE}/inspections`, {
            method: 'POST',
            headers: {
                ...HEADERS,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ metadata: { source: 'web_test' } })
        });

        if (!response.ok) throw new Error('Failed to create inspection');
        
        const data = await response.json();
        currentInspectionId = data.inspection_id;
        
        metaInspectionId.textContent = `ID: ${currentInspectionId}`;
        statusText.textContent = 'Inspection created. Waiting for image.';
        
        btnCreate.textContent = 'Created ✓';
        
        // Enable next step
        step2.classList.remove('disabled');
        fileUpload.disabled = false;
    } catch (error) {
        console.error(error);
        statusText.textContent = `Error: ${error.message}`;
        btnCreate.disabled = false;
        btnCreate.textContent = 'Create Inspection Session';
    }
});

// Enable upload button when file selected
fileUpload.addEventListener('change', () => {
    if (fileUpload.files.length > 0) {
        btnUpload.disabled = false;
    } else {
        btnUpload.disabled = true;
    }
});

// 2. Upload Image
btnUpload.addEventListener('click', async () => {
    if (!fileUpload.files[0] || !currentInspectionId) return;

    try {
        btnUpload.disabled = true;
        btnUpload.textContent = 'Uploading...';
        fileUpload.disabled = true;
        statusText.textContent = 'Uploading image...';

        const formData = new FormData();
        formData.append('file', fileUpload.files[0]);

        const response = await fetch(`${API_BASE}/inspections/${currentInspectionId}/images`, {
            method: 'POST',
            headers: HEADERS,
            body: formData
        });

        if (!response.ok) throw new Error('Failed to upload image');
        
        const data = await response.json();
        
        metaImageId.textContent = `Image ID: ${data.image_id}`;
        statusText.textContent = 'Image uploaded. Ready to run.';
        
        btnUpload.textContent = 'Uploaded ✓';
        
        // Enable next step
        step3.classList.remove('disabled');
        btnRun.disabled = false;
    } catch (error) {
        console.error(error);
        statusText.textContent = `Error: ${error.message}`;
        btnUpload.disabled = false;
        fileUpload.disabled = false;
        btnUpload.textContent = 'Upload Image';
    }
});

// 3. Run Pipeline
btnRun.addEventListener('click', async () => {
    if (!currentInspectionId) return;

    try {
        btnRun.disabled = true;
        btnRun.textContent = 'Starting...';
        statusText.textContent = 'Running pipeline...';

        const response = await fetch(`${API_BASE}/inspections/${currentInspectionId}/run`, {
            method: 'POST',
            headers: {
                ...HEADERS,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        });

        if (!response.ok) throw new Error('Failed to start pipeline');
        
        statusText.textContent = 'Pipeline running in background...';
        btnRun.textContent = 'Running ✓';
        
        // Enable next step
        step4.classList.remove('disabled');
        btnResults.disabled = false;
        
        // Auto poll
        pollReport();
    } catch (error) {
        console.error(error);
        statusText.textContent = `Error: ${error.message}`;
        btnRun.disabled = false;
        btnRun.textContent = 'Start Inspection';
    }
});

// 4. Fetch Report
btnResults.addEventListener('click', () => pollReport());

async function pollReport() {
    if (!currentInspectionId) return;

    try {
        btnResults.disabled = true;
        btnResults.textContent = 'Fetching...';

        const response = await fetch(`${API_BASE}/inspections/${currentInspectionId}/report`, {
            method: 'GET',
            headers: HEADERS
        });

        if (response.status === 404) {
            statusText.textContent = 'Pipeline still running, checking again soon...';
            setTimeout(pollReport, 3000);
            return;
        }

        if (!response.ok) throw new Error('Failed to fetch report');
        
        const data = await response.json();
        
        statusText.textContent = 'Pipeline completed!';
        btnResults.textContent = 'Refreshed ✓';
        btnResults.disabled = false;
        
        resultsContent.style.display = 'block';
        resultsContent.textContent = JSON.stringify(data, null, 2);
    } catch (error) {
        console.error(error);
        statusText.textContent = `Error: ${error.message}`;
        btnResults.disabled = false;
        btnResults.textContent = 'Fetch Report';
    }
}
