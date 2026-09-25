
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
const differenceOutline = document.getElementById('differenceOutline');


// Global vars
let currentAtlasSliceFile = 'slice0001.jpg';
const preloadedImages = [];
let currentImage = displayImage1;
let nextImage = displayImage2;
let brainToClass = {};
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

    classSelectDiff1.innerHTML = '<option value="">-- Select Class --</option>';
    classSelectDiff2.innerHTML = '<option value="">-- Select Class --</option>';

    uniqueClasses.forEach(className => {
        const option1 = document.createElement('option');
        option1.value = className;
        option1.textContent = className;
        classSelectDiff1.appendChild(option1);

        const option2 = document.createElement('option');
        option2.value = className;
        option2.textContent = className;
        classSelectDiff2.appendChild(option2);
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


function displayDifference() {
    const class1   = classSelectDiff1.value;
    const class2   = classSelectDiff2.value;
    const sliceFile = currentAtlasSliceFile;  // e.g. "slice0010.jpg"

    // reset/hide
    differenceImage.style.display  = 'none';
    differenceOutline.style.display = 'none';
    differenceMessage.style.display = 'none';
    differenceMessage.textContent  = '';
    if (initialMessage) initialMessage.style.display = 'none';

    // must have two distinct classes
    if (!class1 || !class2)          { if (initialMessage) initialMessage.style.display = 'block'; return; }
    if (class1 === class2)           { differenceMessage.textContent = 'Please select two different classes'; differenceMessage.style.display = 'block'; return; }

    const available = cls => Object.values(imageDataMap).some(brain => brain.class === cls &&
        Object.values(brain.images || {}).some(slice => slice.atlas === sliceFile));
    if (!available(class1) || !available(class2)) {
        differenceMessage.textContent = 'No shared data at this atlas level.';
        differenceMessage.style.display = 'block';
        return;
    }

    // Attach handlers before setting sources, including cached image loads.
    differenceImage.onload = () => { differenceImage.style.display = 'block'; };
    differenceImage.onerror = () => {
        differenceMessage.textContent = 'Difference image unavailable for this atlas level.';
        differenceMessage.style.display = 'block';
    };
    differenceOutline.onload = () => { differenceOutline.style.display = 'block'; };
    differenceOutline.onerror = () => { differenceOutline.style.display = 'none'; };

    /* ---------- 1.  Set heat‑map source ---------- */
    const diffFolder   = `${class1}_vs_${class2}`;
    const diffBasePath = `${lastPath}/difference_heatmap/`;
    differenceImage.src = `${diffBasePath}${diffFolder}/${sliceFile}`;
    differenceImage.alt = `Difference: ${class1} vs ${class2} - ${sliceFile}`;

    /* ---------- 2.  Set outline source ---------- */
    const sliceNumber  = sliceFile.match(/\d+/)[0];            // "0010"
    differenceOutline.src = `../assets/atlas/outline/outline${sliceNumber}.png`;
    differenceOutline.alt = `Outline - ${sliceFile}`;

}


    buildImageDataMap();
    buildBrainToClass();
    buildClassSelectors();
    preloadAtlasImages();

    const initialSlice = 10;
    currentAtlasSliceFile = `slice${padNumber(initialSlice)}.jpg`;
    sliceSlider.value = initialSlice;
    sliceNumberLabel.textContent = initialSlice;
    updateAtlasImage(initialSlice);
    displayDifference();

    // User changes the slider
    sliceSlider.addEventListener('input', (e) => {
        const sliceNumber = parseInt(e.target.value, 10);
        sliceNumberLabel.textContent = sliceNumber;
        currentAtlasSliceFile = `slice${padNumber(sliceNumber)}.jpg`; 
        updateAtlasImage(sliceNumber); 
        displayDifference();
    });

    // User modify the classes
    classSelectDiff1.addEventListener('change', displayDifference);
    classSelectDiff2.addEventListener('change', displayDifference);


