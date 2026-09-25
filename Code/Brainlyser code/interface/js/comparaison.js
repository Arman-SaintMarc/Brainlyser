// Elements refs for update
const displayImage1 = document.getElementById('displayImage1');
const displayImage2 = document.getElementById('displayImage2');
const overlayMask = document.getElementById('overlayMask'); 
const sliceSlider = document.getElementById('sliceSlider');
const sliceNumberLabel = document.getElementById('sliceNumberLabel');
const classSelect1 = document.getElementById('classSelect1');
const classSelect2 = document.getElementById('classSelect2');
const classComparison1Div = document.getElementById('classComparison1');
const classComparison2Div = document.getElementById('classComparison2');

// Global variables
let currentAtlasSliceFile = 'slice0001.jpg';
const preloadedImages = [];
let currentImage = displayImage1;
let nextImage = displayImage2;
let brainToClass = {};
let assignmentsToAtlasMapping = {};
let imageDataMap = {};

// Helper Functions 
function padNumber(num) { return num.toString().padStart(4, '0'); }

function calculateAverage(arr) { if (!Array.isArray(arr) || arr.length === 0) { return "N/A"; } const sum = arr.reduce((acc, val) => acc + val, 0); const avg = sum / arr.length; return avg.toFixed(3); }

// Brain_slice_data.js processing for extracting stats
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
    const uniqueClasses = [...new Set(Object.values(brainToClass))].sort();

    classSelect1.innerHTML = '<option value="">-- Select Class --</option>';
    classSelect2.innerHTML = '<option value="">-- Select Class --</option>';

    uniqueClasses.forEach(className => {
        const option1 = document.createElement('option');
        option1.value = className;
        option1.textContent = className;
        classSelect1.appendChild(option1);

        const option2 = document.createElement('option');
        option2.value = className;
        option2.textContent = className;
        classSelect2.appendChild(option2);
    });
}


// Update functions when change image slice
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

function renderClassData(className, atlasSliceFile, targetDiv) {
    if (!className) {
        targetDiv.innerHTML = `<p>Select a class</p>`;
        return;
    }

    let html = `<h3>${className}</h3>`;

    html += `<h4>Median reporter</h4>`;
    const inflammationSlices = [];
    const structureSlices = [];
    const inflammationMeans = [];
    const inflammationStds = [];

    for (const brainName in assignmentsToAtlasMapping) {
        if (brainToClass[brainName] === className) {
            const brainMapping = assignmentsToAtlasMapping[brainName];
            for (const brainSliceFile in brainMapping) {
                if (brainMapping[brainSliceFile] === atlasSliceFile) {

                    inflammationSlices.push({
                        brain: brainName,
                        slice: brainSliceFile,
                        path: `${lastPath}/${brainName}/inflammation/${brainSliceFile}`,
                    });

                    structureSlices.push({
                        brain: brainName,
                        slice: brainSliceFile,
                        path: `${lastPath}/${brainName}/structure/${brainSliceFile}`,
                    });

                    const brainData = imageDataMap[brainName];
                    if (brainData?.images?.[brainSliceFile]?.global) {
                        const stats = brainData.images[brainSliceFile].global;
                        if (typeof stats.mean === "number") {
                            inflammationMeans.push(stats.mean);
                        }
                        if (typeof stats.std === "number") {
                            inflammationStds.push(stats.std);
                        }
                    }
                    break; 
                }
            }
        }
    }

    const avgInflammationMean = calculateAverage(inflammationMeans);
    const avgInflammationStd = calculateAverage(inflammationStds);

    if (!inflammationSlices.length) {
        targetDiv.innerHTML = `<h3>${className}</h3><p>No data at this atlas level.</p>`;
        return;
    }

    const medianInflammationImagePath = `${lastPath}/median/${className}/inflammation/${atlasSliceFile}`;

    html += `<div class="assigned-slices-section">`;
    html += `  <div class="big-image-container">`;
    html += `    <img class="big-image" src="${medianInflammationImagePath}" style="max-width: 100%; height: auto; margin-bottom: 10px;" />`;
    html += `  </div>`;
    html += `  <p class="stats">Avg Mean Intensity: ${avgInflammationMean}<br>Avg Std Dev: ${avgInflammationStd}</p>`;

    if (inflammationSlices.length > 0) {
        html += `<h4>Reporter Thumbnails</h4>`;
        html += `<div class="thumbnail-grid inflammation-grid">`;
        inflammationSlices.forEach((item) => {
            html += `<img src="${item.path}" title="${item.brain} - ${item.slice}"
                        onmouseover="this.closest('.assigned-slices-section').querySelector('.big-image').src = this.src"
                        onmouseout="this.closest('.assigned-slices-section').querySelector('.big-image').src = '${medianInflammationImagePath}'" />`;
        });
        html += `</div>`;
    } else {
        html += `<p>No assigned reporter slices found for this class on this atlas slice.</p>`;
    }

    // Build the thumbnail grid for structure slices
    if (structureSlices.length > 0) {
        html += `<h4 style="margin-top: 20px;">Structure Thumbnails</h4>`;
        html += `<div class="thumbnail-grid structure-grid">`;
        structureSlices.forEach((item) => {
            html += `<img src="${item.path}" title="${item.brain} - ${item.slice}"
                        onmouseover="this.closest('.assigned-slices-section').querySelector('.big-image').src = this.src"
                        onmouseout="this.closest('.assigned-slices-section').querySelector('.big-image').src = '${medianInflammationImagePath}'" />`;
        });
        html += `</div>`;
    } else {
        html += `<p>No assigned structure slices found for this class on this atlas slice.</p>`;
    }

    html += `</div>`;

    // Update the target div with the constructed HTML.
    targetDiv.innerHTML = html;
}





function displayComparison() {
    const selectedClass1 = classSelect1.value;
    const selectedClass2 = classSelect2.value;

    renderClassData(selectedClass1, currentAtlasSliceFile, classComparison1Div);
    renderClassData(selectedClass2, currentAtlasSliceFile, classComparison2Div);
}



        buildImageDataMap();
        buildBrainToClass();
        buildAssignmentsMapping();
        buildClassSelectors();

        preloadAtlasImages(); 

        const initialSlice = 10;
        currentAtlasSliceFile = `slice${padNumber(initialSlice)}.jpg`;
        sliceSlider.value = initialSlice;
        sliceNumberLabel.textContent = initialSlice;

        updateAtlasImage(initialSlice); 
        displayComparison(); 



    // If user changes the slider
    sliceSlider.addEventListener('input', (e) => {
        const sliceNumber = parseInt(e.target.value, 10);
        sliceNumberLabel.textContent = sliceNumber;
        currentAtlasSliceFile = `slice${padNumber(sliceNumber)}.jpg`;
        updateAtlasImage(sliceNumber); 
        displayComparison();
    });

    // If user changes the class selected
    classSelect1.addEventListener('change', displayComparison);
    classSelect2.addEventListener('change', displayComparison);

