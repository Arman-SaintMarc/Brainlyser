// Elements refs for update
const totalBrainsEl = document.getElementById('totalBrains');
const totalClassesEl = document.getElementById('totalClasses');
const totalSlicesEl = document.getElementById('totalSlices');
const plotlyHistogramEl = document.getElementById('plotlyClassHistogram');
const plotlyScatterEl = document.getElementById('plotlyRegionScatter');
const plotlyHeatmapFEl = document.getElementById('plotlyHeatmapF');
const plotlyHeatmapMEl = document.getElementById('plotlyHeatmapM');
const smoothToggleCheckbox = document.getElementById('smoothToggle');
const heatmapErrorFEl = document.getElementById('heatmapErrorF');
const heatmapErrorMEl = document.getElementById('heatmapErrorM');

// Constants 
const REGION_MAPPING = { "9": "1065_HB", "8": "1089_HPF", "7": "1097_HY", "6": "313_MB", "5": "315_Isocortex", "4": "512_CB", "3": "549_TH", "2": "623_CNU", "1": "698_OLF" };
const WHITE_COLOR = '#FFFFFF';
const LIGHT_GREY_COLOR = '#AAAAAA';
const HEATMAP_COLORSCALE_DIFF = 'RdBu_r';
const MAX_SLICES = 220;

// Helper Functions for Stats
function calculateMean(arr) { 
    if (!Array.isArray(arr) || arr.length === 0) return NaN; 
    const sum = arr.reduce((acc, val) => acc + val, 0); 
    return sum / arr.length; 
}
function calculateStdDev(arr) { 
    if (!Array.isArray(arr) || arr.length < 1) return NaN; 
    const mean = calculateMean(arr); 
    const variance = arr.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) / arr.length; 
    return Math.sqrt(variance); 
}
function extractSliceNumber(filename) { 
    if (!filename) return null; 
    const match = filename.match(/slice(\d+)/); 
    return match ? parseInt(match[1], 10) : null; 
}
function calculateMaxAbs(matrix) { 
    let maxAbs = 0; 
    if(!matrix) return 0; 
    for (const row of matrix) { 
        for (const val of row) { 
            if (!isNaN(val)) { 
                maxAbs = Math.max(maxAbs, Math.abs(val)); 
            } 
        } 
    } 
    return maxAbs; 
}
function subtractMatrices(matrixA, matrixB) { 
    if (!matrixA || !matrixB || matrixA.length !== matrixB.length || matrixA[0]?.length !== matrixB[0]?.length) { 
        console.error("Cannot subtract matrices of different dimensions."); 
        return null; 
    } 
    const rows = matrixA.length; 
    const cols = matrixA[0].length; 
    const result = Array(rows).fill(null).map(() => Array(cols).fill(NaN)); 
    for (let i = 0; i < rows; i++) { 
        for (let j = 0; j < cols; j++) { 
            if (typeof matrixA[i][j] === 'number' && typeof matrixB[i][j] === 'number') { 
                result[i][j] = matrixA[i][j] - matrixB[i][j]; 
            } 
        } 
    } 
    return result; 
}
function interpolateGaps(arr) { 
    if (!arr || arr.length === 0) return []; 
    const result = [...arr]; 
    let lastValidIndex = -1; 
    for (let i = 0; i < result.length; i++) { 
        if (!isNaN(result[i])) { 
            if (lastValidIndex !== -1 && i > lastValidIndex + 1) { 
                const x1 = lastValidIndex; 
                const y1 = result[x1]; 
                const x2 = i; 
                const y2 = result[x2]; 
                const gapLength = x2 - x1; 
                for (let j = x1 + 1; j < x2; j++) { 
                    if (isNaN(result[j])) { 
                        result[j] = y1 + (y2 - y1) * (j - x1) / gapLength; 
                    } 
                } 
            } 
            lastValidIndex = i; 
        } 
    } 
    return result; 
}

// Global vars
let isInterpolatedView = false;
let classCounts = {};
let totalSlicesProcessed = 0;
let scatterPlotData = [];
let heatmapsByClassRaw = {};
let heatmapsByClassInterpolated = {};
let diffHeatmapFRaw = null, diffHeatmapFInterpolated = null;
let diffHeatmapMRaw = null, diffHeatmapMInterpolated = null;
let globalDiffAbsMax = 0;
let regionListReference = [];
const xGrid = Array.from({length: MAX_SLICES}, (_, i) => i + 1);
const plotlyConfig = { responsive: true, displayModeBar: false };

// --- New Helper Functions for Automatic Class Handling ---

// Global mapping for disease colors; keys are disease codes (e.g., "AD", "HT")
const diseaseColorPairs = {};
const defaultDiseaseColorPairs = [
  {F: "#2865B4", M: "#708040"},
  {F: "#A64B9B", M: "#9B4BA6"},
  {F: "#5A8F3E", M: "#8F5A3E"},
  {F: "#3E8F8F", M: "#8F3E3E"}
];

function getSymbolForClass(cls) {
    // Return "circle" for female classes and "square" for male classes
    if (cls.endsWith("-F")) return "circle";
    if (cls.endsWith("-M")) return "square";
    return "circle";
}

function getColorForClass(cls) {
    if (cls.startsWith("CT-")) {
        // Controls: use fixed colors
        return cls.endsWith("-F") ? "#555555" : "#303030";
    } else {
        // Disease positive: assign based on disease code
        const diseaseCode = cls.split("-")[0];
        if (!diseaseColorPairs[diseaseCode]) {
            // Assign a new pair from the default palette (cycling through if needed)
            diseaseColorPairs[diseaseCode] = defaultDiseaseColorPairs[Object.keys(diseaseColorPairs).length % defaultDiseaseColorPairs.length];
        }
        return cls.endsWith("-F") ? diseaseColorPairs[diseaseCode].F : diseaseColorPairs[diseaseCode].M;
    }
}

// --- End of New Helpers ---

// Plotting heatmaps
function plotDifferenceHeatmaps() {
    const comparisonPairs = [];

    globalDiffAbsMax = 0;
    for (const diseaseClass in heatmapsByClassRaw) {
        if (diseaseClass.startsWith("CT-")) continue;  // Skip controls
        const controlClass = diseaseClass.endsWith("-F") ? "CT-F" : "CT-M";
        if (!heatmapsByClassRaw[controlClass]) continue; // Skip if matching control not found

        // Compute difference for raw data
        const diffRaw = subtractMatrices(heatmapsByClassRaw[diseaseClass], heatmapsByClassRaw[controlClass]);
        if (diffRaw) {
            globalDiffAbsMax = Math.max(globalDiffAbsMax, calculateMaxAbs(diffRaw));
        }

        // Compute difference for interpolated data (if available)
        if (heatmapsByClassInterpolated[diseaseClass] && heatmapsByClassInterpolated[controlClass]) {
            const diffInterpolated = subtractMatrices(heatmapsByClassInterpolated[diseaseClass], heatmapsByClassInterpolated[controlClass]);
            if (diffInterpolated) {
                globalDiffAbsMax = Math.max(globalDiffAbsMax, calculateMaxAbs(diffInterpolated));
            }
        }
    }

    // Avoid a zero scale
    if (globalDiffAbsMax === 0) {
        globalDiffAbsMax = 0.01;
    }

    // Loop through disease-positive classes (skip controls)
    for (const diseaseClass in heatmapsByClassRaw) {
        if (diseaseClass.startsWith("CT-")) continue;
        
        // Determine gender from the class suffix
        let gender = "";
        if (diseaseClass.endsWith("-F")) {
            gender = "-F";
        } else if (diseaseClass.endsWith("-M")) {
            gender = "-M";
        } else {
            continue;
        }
        
        // Find corresponding control based on gender (e.g., CT-F for -F and CT-M for -M)
        const controlClass = gender === "-F" ? "CT-F" : "CT-M";
        if (!heatmapsByClassRaw[controlClass]) continue;
        
        const diffDataRaw = subtractMatrices(heatmapsByClassRaw[diseaseClass], heatmapsByClassRaw[controlClass]);
        const diffDataInterpolated = subtractMatrices(heatmapsByClassInterpolated[diseaseClass], heatmapsByClassInterpolated[controlClass]);

        // Use target divs according to gender
        let targetDiv, errorDiv;
        if (gender === "-F") {
            targetDiv = plotlyHeatmapFEl;
            errorDiv = heatmapErrorFEl;
        } else if (gender === "-M") {
            targetDiv = plotlyHeatmapMEl;
            errorDiv = heatmapErrorMEl;
        }
        
        comparisonPairs.push({
            name: `${diseaseClass} vs ${controlClass}`,
            diffDataRaw,
            diffDataInterpolated,
            targetDiv,
            errorDiv,
            ad: diseaseClass,
            ct: controlClass
        });
    }

    comparisonPairs.forEach(pair => {
        const { name, diffDataRaw, diffDataInterpolated, targetDiv, errorDiv, ad, ct } = pair;let gender = "";
        if (ad.endsWith("-F") && document.getElementById("heatmapTitleF")) {
            document.getElementById("heatmapTitleF").textContent = `Reporter Difference (${ad} vs ${ct})`;
        }
        if (ad.endsWith("-M") && document.getElementById("heatmapTitleM")) {
            document.getElementById("heatmapTitleM").textContent = `Reporter Difference (${ad} vs ${ct})`;
        }

        if (errorDiv) errorDiv.style.display = 'none';
        if (targetDiv) targetDiv.innerHTML = '';
        if (!targetDiv) { 
            console.error(`Target div for ${name} heatmap not found.`); 
            return; 
        }

        const diffData = isInterpolatedView ? diffDataInterpolated : diffDataRaw;

        if (!diffData) {
            const viewType = isInterpolatedView ? 'interpolated' : 'raw';
            console.warn(`Selected difference data (${viewType}) for ${name} is not available.`);
            if (errorDiv) { 
                errorDiv.textContent = `Data not available for ${name} (${viewType}).`; 
                errorDiv.style.display = 'block'; 
            }
            return;
        }

        const zmin = -globalDiffAbsMax;
        const zmax = globalDiffAbsMax;

        const heatmapTrace = {
            z: diffData,
            x: xGrid,
            y: regionListReference,
            type: 'heatmap',
            colorscale: HEATMAP_COLORSCALE_DIFF,
            zmin: zmin,
            zmax: zmax,
            colorbar: { 
                title: `Δ (${ad} − ${ct})`, 
                titlefont: { color: LIGHT_GREY_COLOR }, 
                tickfont: { color: LIGHT_GREY_COLOR } 
            },
            hoverongaps: false,
            hovertemplate: "Slice: %{x}<br>Region: %{y}<br>Δ Reporter: %{z:.2f}<extra></extra>"
        };
        const heatmapLayout = {
            height: null,
            xaxis: { 
                title: 'Atlas Slice Index', 
                titlefont: { color: WHITE_COLOR }, 
                tickfont: { color: LIGHT_GREY_COLOR }, 
                showgrid: false, 
                zeroline: false 
            },
            yaxis: { 
                title: 'Brain Region', 
                titlefont: { color: WHITE_COLOR }, 
                tickfont: { color: LIGHT_GREY_COLOR }, 
                showgrid: false, 
                zeroline: false, 
                type: 'category', 
                categoryorder: 'array', 
                categoryarray: regionListReference.slice().reverse() 
            },
            paper_bgcolor: 'rgba(0,0,0,0)', 
            plot_bgcolor: 'rgba(18, 18, 18, 0.5)',
            font: { color: WHITE_COLOR },
            margin: { t: 20, b: 60, l: 120, r: 30 }
        };

        Plotly.newPlot(targetDiv, [heatmapTrace], heatmapLayout, plotlyConfig);
    });
}


// Brain_slice_data.js processing for extracting stats
try {
    // Reset/initialize stats
    classCounts = {}; 
    totalSlicesProcessed = 0; 
    scatterPlotData = [];
    heatmapRawData = {}; 
    heatmapsByClassRaw = {}; 
    heatmapsByClassInterpolated = {};
    diffHeatmapFRaw = null; 
    diffHeatmapFInterpolated = null;
    diffHeatmapMRaw = null; 
    diffHeatmapMInterpolated = null;
    globalDiffAbsMax = 0; 
    regionListReference = [];

    imageData.forEach(brainObject => {
        const brainId = Object.keys(brainObject)[0]; 
        const brainDataArray = brainObject[brainId]; 
        if (!brainDataArray || !Array.isArray(brainDataArray) || brainDataArray.length === 0) return; 
        const brainInfo = brainDataArray[0]; 
        const brainClass = brainInfo.class || 'Unknown'; 
        const images = brainInfo.images || {}; 
        classCounts[brainClass] = (classCounts[brainClass] || 0) + 1; 
        totalSlicesProcessed += Object.keys(images).length; 
        const regionMeansPerBrain = {}; 
        for (const imgKey in images) { 
            const sliceData = images[imgKey] || {}; 
            const atlasFile = sliceData.atlas; 
            const sliceNum = extractSliceNumber(atlasFile); 
            if (sliceNum === null || sliceNum < 1 || sliceNum > MAX_SLICES) continue;
            for (const key in sliceData) { 
                if (key === "atlas") continue; 
                const metrics = sliceData[key]; 
                if (metrics && typeof metrics.median === 'number') { 
                    const meanVal = metrics.median; 
                    if (!regionMeansPerBrain[key]) { 
                        regionMeansPerBrain[key] = []; 
                    } 
                    regionMeansPerBrain[key].push(metrics.median); 
                    if (key.startsWith("brainRegion")) { 
                        const regionNumStr = key.replace("brainRegion", ""); 
                        const regionName = REGION_MAPPING[regionNumStr] || key; 
                        if (!heatmapRawData[brainClass]) heatmapRawData[brainClass] = {}; 
                        if (!heatmapRawData[brainClass][regionName]) heatmapRawData[brainClass][regionName] = {}; 
                        if (!heatmapRawData[brainClass][regionName][sliceNum]) heatmapRawData[brainClass][regionName][sliceNum] = []; 
                        heatmapRawData[brainClass][regionName][sliceNum].push(meanVal); 
                    } 
                } 
            } 
        } 
        for (const regionKey in regionMeansPerBrain) { 
            const meansArray = regionMeansPerBrain[regionKey]; 
            const aggregatedMean = calculateMean(meansArray); 
            const aggregatedStd = calculateStdDev(meansArray); 
            let mappedRegion = regionKey; 
            if (regionKey.startsWith("brainRegion")) { 
                mappedRegion = REGION_MAPPING[regionKey.replace("brainRegion", "")] || regionKey; 
            } 
            if (!isNaN(aggregatedMean)) { 
                scatterPlotData.push({ 
                    brain: brainId, 
                    class: brainClass, 
                    region: mappedRegion, 
                    aggregatedMean: aggregatedMean, 
                    aggregatedStd: isNaN(aggregatedStd) ? 'N/A' : aggregatedStd.toFixed(3) 
                }); 
            } 
        }
    });

    const uniqueClasses = Object.keys(classCounts).sort();
    const totalClasses = uniqueClasses.length;
    const totalBrains = imageData.length;

    // Update UI stats
    if(totalBrainsEl) totalBrainsEl.textContent = totalBrains;
    if(totalClassesEl) totalClassesEl.textContent = totalClasses;
    if(totalSlicesEl) totalSlicesEl.textContent = totalSlicesProcessed;

    // Plotting class histogram
    const yValues = uniqueClasses.map(cls => classCounts[cls] || 0);
    const histogramTrace = { 
        x: uniqueClasses, 
        y: yValues, 
        type: 'bar', 
        marker: { color: uniqueClasses.map(cls => getColorForClass(cls) || '#cccccc') }, 
        text: yValues.map(String), 
        textposition: 'outside', 
        textfont: { color: WHITE_COLOR, size: 14 }, 
        hoverinfo: 'x+y' 
    };
    const histogramLayout = { 
        title: { text: 'Brains per Class', font: { color: WHITE_COLOR } }, 
        xaxis: { title: 'Class', titlefont: { color: WHITE_COLOR }, tickfont: { color: LIGHT_GREY_COLOR }, showgrid: false, zeroline: false }, 
        yaxis: { title: 'Number of Brains', showticklabels: false, showgrid: false, zeroline: false, titlefont: { color: WHITE_COLOR } }, 
        margin: { t: 40, b: 40, l: 50, r: 20 }, 
        paper_bgcolor: 'rgba(0,0,0,0)', 
        plot_bgcolor: 'rgba(0,0,0,0)', 
        font: { color: WHITE_COLOR } 
    };
    Plotly.newPlot(plotlyHistogramEl, [histogramTrace], histogramLayout, plotlyConfig);

    // Plotting scatter for outlier detection
    const uniqueRegions = [...new Set(scatterPlotData.map(d => d.region))].sort();
    const regionToNumeric = Object.fromEntries(uniqueRegions.map((region, i) => [region, i]));
    const processedScatterData = scatterPlotData.map(d => ({
        ...d, 
        region_num: regionToNumeric[d.region], 
        region_jitter: regionToNumeric[d.region] + (Math.random() * 0.5 - 0.25),
        symbol: getSymbolForClass(d.class),
        color: getColorForClass(d.class),
        hoverText: `Brain: ${d.brain}<br>Region: ${d.region}<br>Median: ${d.aggregatedMean.toFixed(3)}<br>StdDev: ${d.aggregatedStd}`
    }));

    const scatterTrace = { 
        x: processedScatterData.map(d => d.region_jitter), 
        y: processedScatterData.map(d => d.aggregatedMean), 
        mode: 'markers', 
        type: 'scatter', 
        text: processedScatterData.map(d => d.hoverText), 
        hoverinfo: 'text', 
        marker: { 
            size: 10, 
            color: processedScatterData.map(d => d.color), 
            symbol: processedScatterData.map(d => d.symbol) 
        },
        showlegend: false 
    };
    const scatterLayout = { 
        title: { text: 'Median Reporter by Brain Region', font: { color: WHITE_COLOR } }, 
        height: null, 
        xaxis: { 
            title: 'Region', 
            tickmode: 'array', 
            tickvals: Object.values(regionToNumeric), 
            ticktext: Object.keys(regionToNumeric), 
            showgrid: false, 
            zeroline: false, 
            titlefont: { color: WHITE_COLOR }, 
            tickfont: { color: LIGHT_GREY_COLOR } 
        }, 
        yaxis: { 
            title: 'Aggregated Median Reporter', 
            showgrid: false, 
            zeroline: false, 
            titlefont: { color: WHITE_COLOR }, 
            tickfont: { color: LIGHT_GREY_COLOR } 
        }, 
        paper_bgcolor: 'rgba(0,0,0,0)', 
        plot_bgcolor: 'rgba(0,0,0,0)', 
        font: { color: WHITE_COLOR, family: 'Inter, sans-serif', size: 12 }, 
        margin: { t: 50, b: 100, l: 60, r: 30 }, 
        showlegend: true, 
        legend: { 
            title: { text: 'Brain Class', font: { color: WHITE_COLOR } }, 
            bgcolor: 'rgba(30, 30, 30, 0.8)', 
            bordercolor: 'var(--border-color)', 
            borderwidth: 1, 
            font: { color: LIGHT_GREY_COLOR } 
        } 
    };
    const legendTraces = uniqueClasses.map(cls => ({
        x: [null],
        y: [null],
        name: cls,
        mode: 'markers',
        marker: { 
            symbol: getSymbolForClass(cls), 
            color: getColorForClass(cls), 
            size: 10 
        }
    }));
    const classTraces = uniqueClasses.map(cls => {
        const pts = processedScatterData.filter(d => d.class === cls);
      
        return {
          name: cls,            // label appears in legend
          x: pts.map(p => p.region_jitter),
          y: pts.map(p => p.aggregatedMean),
          mode: 'markers',
          type: 'scatter',
          text: pts.map(p => p.hoverText),
          hoverinfo: 'text',
          marker: {
            size: 10,
            color: getColorForClass(cls),
            symbol: getSymbolForClass(cls)
          }
        };
      });
      
    Plotly.newPlot(plotlyScatterEl, classTraces, scatterLayout, plotlyConfig);

    // Process heatmap data
    const allRegions = new Set();
    Object.values(heatmapRawData).forEach(regions => { 
        Object.keys(regions).forEach(region => allRegions.add(region)); 
    });
    regionListReference = Array.from(allRegions).sort();
    for (const cls in heatmapRawData) {
        const numRegions = regionListReference.length;
        const rawHeatmapArray = Array(numRegions).fill(null).map(() => Array(MAX_SLICES).fill(NaN));
        const interpolatedHeatmapArray = Array(numRegions).fill(null).map(() => Array(MAX_SLICES).fill(NaN));
        regionListReference.forEach((region, regionIndex) => {
            const rawRow = rawHeatmapArray[regionIndex];
            if (heatmapRawData[cls][region]) {
                const regionSliceData = heatmapRawData[cls][region];
                for (let sliceNum = 1; sliceNum <= MAX_SLICES; sliceNum++) {
                    if (regionSliceData[sliceNum] && regionSliceData[sliceNum].length > 0) {
                        rawRow[sliceNum - 1] = calculateMean(regionSliceData[sliceNum]);
                    }
                }
            }
            interpolatedHeatmapArray[regionIndex] = interpolateGaps(rawRow);
        });
        heatmapsByClassRaw[cls] = rawHeatmapArray;
        heatmapsByClassInterpolated[cls] = interpolatedHeatmapArray;
        console.log(`Processed raw and interpolated heatmaps for class: ${cls}`);
    }

    // Compute global difference scale for heatmaps (comparing disease vs control)
    globalDiffAbsMax = 0;
    if (heatmapsByClassRaw["AD-F"] && heatmapsByClassRaw["CT-F"]) {
        diffHeatmapFRaw = subtractMatrices(heatmapsByClassRaw["AD-F"], heatmapsByClassRaw["CT-F"]);
        if (diffHeatmapFRaw) globalDiffAbsMax = Math.max(globalDiffAbsMax, calculateMaxAbs(diffHeatmapFRaw));
    }
    if (heatmapsByClassRaw["AD-M"] && heatmapsByClassRaw["CT-M"]) {
        diffHeatmapMRaw = subtractMatrices(heatmapsByClassRaw["AD-M"], heatmapsByClassRaw["CT-M"]);
        if (diffHeatmapMRaw) globalDiffAbsMax = Math.max(globalDiffAbsMax, calculateMaxAbs(diffHeatmapMRaw));
    }
    if (heatmapsByClassInterpolated["AD-F"] && heatmapsByClassInterpolated["CT-F"]) {
        diffHeatmapFInterpolated = subtractMatrices(heatmapsByClassInterpolated["AD-F"], heatmapsByClassInterpolated["CT-F"]);
        if (diffHeatmapFInterpolated) globalDiffAbsMax = Math.max(globalDiffAbsMax, calculateMaxAbs(diffHeatmapFInterpolated));
    }
    if (heatmapsByClassInterpolated["AD-M"] && heatmapsByClassInterpolated["CT-M"]) {
        diffHeatmapMInterpolated = subtractMatrices(heatmapsByClassInterpolated["AD-M"], heatmapsByClassInterpolated["CT-M"]);
        if (diffHeatmapMInterpolated) globalDiffAbsMax = Math.max(globalDiffAbsMax, calculateMaxAbs(diffHeatmapMInterpolated));
    }
    if (globalDiffAbsMax === 0) { 
        globalDiffAbsMax = 0.01; 
    }

    // Plotting heatmaps based on selected view (raw or interpolated)
    isInterpolatedView = smoothToggleCheckbox.checked;
    plotDifferenceHeatmaps();

    smoothToggleCheckbox.addEventListener('change', () => {
        isInterpolatedView = smoothToggleCheckbox.checked;
        plotDifferenceHeatmaps(); // Re-plot when toggle changes
    });

} catch (error) {
    console.error("Error: ", error);
}
