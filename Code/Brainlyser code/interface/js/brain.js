// Ref elem
const displayImage1 = document.getElementById('displayImage1');
const displayImage2 = document.getElementById('displayImage2');
const overlayMask = document.getElementById('overlayMask');
const sliceSlider = document.getElementById('sliceSlider');
const sliceNumberLabel = document.getElementById('sliceNumberLabel');
const classSelectDiff1 = document.getElementById('classSelectDiff1');
const classSelectDiff2 = document.getElementById('classSelectDiff2');
const differenceDisplayArea = document.getElementById('differenceDisplayArea');
const differenceImage = document.getElementById('differenceImage');
const differenceMessage = document.getElementById('differenceMessage');
const initialMessage = differenceDisplayArea.querySelector('p:not(.error-message)');

// Global vars
let currentAtlasSliceFile = 'slice0001.jpg';
const preloadedImages = [];
let currentImage = displayImage1;
let nextImage = displayImage2;
let brainToClass = {};
let imageDataMap = {};
let assignmentsToAtlasMapping = {}; // Will hold the mapping from brain slices to atlas slices

// Helper Functions 
function padNumber(num) { 
    return num.toString().padStart(4, '0'); 
}

function calculateAverage(arr) { 
    if (!Array.isArray(arr) || arr.length === 0) { 
        return "N/A"; 
    } 
    const sum = arr.reduce((acc, val) => acc + val, 0); 
    const avg = sum / arr.length; 
    return avg.toFixed(3); 
}

// Process imageData array to build a mapping.
function buildImageDataMap() {
    imageDataMap = {};
    imageData.forEach(item => {
        const brainName = Object.keys(item)[0];
        if (brainName && item[brainName] && Array.isArray(item[brainName]) && item[brainName].length > 0) {
            imageDataMap[brainName] = item[brainName][0];
        }
    });
}

function buildBrainToClass() {
    brainToClass = {};
    for (const brainName in imageDataMap) {
        if (imageDataMap[brainName] && imageDataMap[brainName].class) {
            brainToClass[brainName] = imageDataMap[brainName].class;
        }
    }
}

function buildAssignmentsMapping() {
    assignmentsToAtlasMapping = {};
    for (const brainName in imageDataMap) {
        const brainData = imageDataMap[brainName];
        if (brainData && brainData.images) {
            assignmentsToAtlasMapping[brainName] = {};
            for (const brainSliceFile in brainData.images) {
                const sliceData = brainData.images[brainSliceFile];
                if (sliceData && sliceData.atlas) {
                    assignmentsToAtlasMapping[brainName][brainSliceFile] = sliceData.atlas;
                }
            }
        }
    }
}

function preloadAtlasImages() {
    const maxSlices = parseInt(sliceSlider.max, 10);
    for (let i = 1; i <= maxSlices; i++) {
        const padded = padNumber(i);
        const img = new Image();
        img.src = `../assets/atlas/structure/slice${padded}.jpg`;
        preloadedImages.push(img);
    }
    console.log(`${preloadedImages.length} Atlas images preloaded.`);
}

function buildClassSelectors() {
    classSelectDiff1.innerHTML = '<option value="">-- Select Brain --</option>';
    Object.entries(brainToClass).forEach(([brainName, className]) => {
        const option = document.createElement('option');
        option.value = brainName;
        option.textContent = `${brainName} - ${className}`;
        classSelectDiff1.appendChild(option);
    });
}

// Update the atlas image when the slice changes.
function updateAtlasImage(sliceNumber) {
    const paddedSlice = padNumber(sliceNumber);
    const atlasImagePath = `../assets/atlas/structure/slice${paddedSlice}.jpg`;
    const maskImagePath = `../assets/atlas/colored_mask/slice${paddedSlice}.png`;

    const preloadedIndex = sliceNumber - 1;
    if (preloadedIndex < 0 || preloadedIndex >= preloadedImages.length || !preloadedImages[preloadedIndex]) {
        nextImage.src = atlasImagePath;
    } else {
        nextImage.src = preloadedImages[preloadedIndex].src;
    }
    overlayMask.src = maskImagePath;

    nextImage.onload = () => {
        nextImage.style.opacity = 1;
        currentImage.style.opacity = 0;
        nextImage.classList.add('active');
        nextImage.classList.remove('inactive');
        currentImage.classList.add('inactive');
        currentImage.classList.remove('active');
        let temp = currentImage;
        currentImage = nextImage;
        nextImage = temp;
    };
}

// Render data for the selected brain (using assignmentsToAtlasMapping).
function renderClassData(selectedBrain, atlasSliceFile, targetDiv) {
    // If no brain is selected, instruct the user accordingly.
    if (!selectedBrain) {
        targetDiv.innerHTML = `<p style="text-align:center;">Select a brain</p>`;
        return;
    }

    // Start with a centered heading.
    let html = `<h3 style="text-align:center;">${selectedBrain}</h3>`;

    // Arrays for gathering slice data.
    const inflammationSlices = [];
    const structureSlices = [];
    const inflammationMeans = [];
    const inflammationStds = [];

    // Get the mapping for the selected brain.
    const brainMapping = assignmentsToAtlasMapping[selectedBrain];
    if (brainMapping) {
        // If atlas slice 1 is selected, display all slices.
        if (atlasSliceFile === "slice0001.jpg") {
            for (const brainSliceFile in brainMapping) {
                inflammationSlices.push({
                    brain: selectedBrain,
                    slice: brainSliceFile,
                    path: `${lastPath}/${selectedBrain}/inflammation/${brainSliceFile}`
                });
                structureSlices.push({
                    brain: selectedBrain,
                    slice: brainSliceFile,
                    path: `${lastPath}/${selectedBrain}/structure/${brainSliceFile}`
                });
                const brainData = imageDataMap[selectedBrain];
                if (brainData?.images?.[brainSliceFile]?.global) {
                    const stats = brainData.images[brainSliceFile].global;
                    if (typeof stats.mean === "number") {
                        inflammationMeans.push(stats.mean);
                    }
                    if (typeof stats.std === "number") {
                        inflammationStds.push(stats.std);
                    }
                }
            }
        } else {
            // For any other slice, show only the matching brain slice.
            for (const brainSliceFile in brainMapping) {
                if (brainMapping[brainSliceFile] === atlasSliceFile) {
                    inflammationSlices.push({
                        brain: selectedBrain,
                        slice: brainSliceFile,
                        path: `${lastPath}/${selectedBrain}/inflammation/${brainSliceFile}`
                    });
                    structureSlices.push({
                        brain: selectedBrain,
                        slice: brainSliceFile,
                        path: `${lastPath}/${selectedBrain}/structure/${brainSliceFile}`
                    });
                    const brainData = imageDataMap[selectedBrain];
                    if (brainData?.images?.[brainSliceFile]?.global) {
                        const stats = brainData.images[brainSliceFile].global;
                        if (typeof stats.mean === "number") {
                            inflammationMeans.push(stats.mean);
                        }
                        if (typeof stats.std === "number") {
                            inflammationStds.push(stats.std);
                        }
                    }
                    break; // Only one matching slice per brain if not atlas slice 1.
                }
            }
        }
    } else {
        targetDiv.innerHTML = `<p style="text-align:center;">No data available for ${selectedBrain}</p>`;
        return;
    }

    // Compute average statistics.
    const avgInflammationMean = calculateAverage(inflammationMeans);
    const avgInflammationStd = calculateAverage(inflammationStds);

    // Set the default (hover) image to the first structure slice, if available.
    let defaultHoverImage = "";
    if (structureSlices.length > 0) {
        defaultHoverImage = structureSlices[0].path;
    }

    // Assemble the HTML with a responsive container.
    html += `<div class="assigned-slices-section" style="text-align: center; max-height: 80vh; overflow-y: auto; margin: 0 auto;">`;
    html += `  <div class="big-image-container" style="margin: 0 auto;">`;
    if (defaultHoverImage) html += `    <img class="big-image" src="${defaultHoverImage}" style="max-width: 60%; height: auto; margin-bottom: 10px; display: block; margin-left: auto; margin-right: auto;" />`;
    html += `  </div>`;
    html += `  <p class="stats" style="text-align:center;">Avg Mean Intensity: ${avgInflammationMean}<br>Avg Std Dev: ${avgInflammationStd}</p>`;

    // Inflammation thumbnails.
    if (inflammationSlices.length > 0) {
        html += `<h4 style="text-align:center;">Reporter Thumbnails</h4>`;
        html += `<div class="thumbnail-grid inflammation-grid" style="text-align:center;">`;
        inflammationSlices.forEach((item) => {
            html += `<img src="${item.path}" title="${item.brain} - ${item.slice}"
                        onmouseover="this.closest('.assigned-slices-section').querySelector('.big-image').src = this.src"
                        style="cursor:pointer; margin: 5px;" />`;
        });
        html += `</div>`;
    } else {
        html += `<p style="text-align:center;">No assigned reporter slices found for this brain on this atlas slice.</p>`;
    }

    // Structure thumbnails.
    if (structureSlices.length > 0) {
        html += `<h4 style="margin-top: 20px; text-align:center;">Structure Thumbnails</h4>`;
        html += `<div class="thumbnail-grid structure-grid" style="text-align:center;">`;
        structureSlices.forEach((item) => {
            html += `<img src="${item.path}" title="${item.brain} - ${item.slice}"
                        onmouseover="this.closest('.assigned-slices-section').querySelector('.big-image').src = this.src"
                        style="cursor:pointer; margin: 5px;" />`;
        });
        html += `</div>`;
    } else {
        html += `<p style="text-align:center;">No assigned structure slices found for this brain on this atlas slice.</p>`;
    }
    html += `</div>`;

    // Update the target element.
    targetDiv.innerHTML = html;
}

// ----- INITIALIZATION & EVENT BINDING -----

// Build the data mappings and selectors.
buildImageDataMap();
buildBrainToClass();
buildClassSelectors();
buildAssignmentsMapping(); // Build the mapping for brain-to-atlas assignments.
preloadAtlasImages();

// Set the initial atlas slice.
const initialSlice = 10;
currentAtlasSliceFile = `slice${padNumber(initialSlice)}.jpg`;
sliceSlider.value = initialSlice;
sliceNumberLabel.textContent = initialSlice;
updateAtlasImage(initialSlice);

// Initially, render the data area with a prompt to select a brain.
renderClassData('', currentAtlasSliceFile, differenceDisplayArea);

// When the user changes the slice slider...
sliceSlider.addEventListener('input', (e) => {
    const sliceNumber = parseInt(e.target.value, 10);
    sliceNumberLabel.textContent = sliceNumber;
    currentAtlasSliceFile = `slice${padNumber(sliceNumber)}.jpg`;
    updateAtlasImage(sliceNumber);
    
    // If a brain is selected, update the displayed data.
    const selectedBrain = classSelectDiff1.value;
    if (selectedBrain) {
        renderClassData(selectedBrain, currentAtlasSliceFile, differenceDisplayArea);
    }
});

// When the user selects a brain from the dropdown...
classSelectDiff1.addEventListener('change', (e) => {
    console.log("Selected brain:", e.target.value);
    const selectedBrain = e.target.value;
    renderClassData(selectedBrain, currentAtlasSliceFile, differenceDisplayArea);
});
