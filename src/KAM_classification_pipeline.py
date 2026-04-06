# Set your home directory where you will be working
homeDir = HOME_DIRECTORY_HERE # type: ignore

# Set the directory where the orthomosaics are stored 
# (can be the same or different from home, I keep orthos on external drives due to their size)
orthoDir= ORTHO_DIRECTORY_HERE # type: ignore

# Select which AOI (areas of interest) to run the tool for. 
# This takes "AOI" and "AOI_name", with "AOI" being the acronym and "AOI_name" being the full name with underscores
datasets = [
    # ("SJI", "San_Juan_Islands"),
    # ("NPS", "North_Puget_Sound"),
    # ("AQR", "Aquatic_Reserves"),
    # ("SJFE", "Strait_of_Juan_de_Fuca_East"),
    # ("SJFW", "Strait_of_Juan_de_Fuca_West"),
    # ("TAC", "Tacoma_Narrows"),
    ("SWH", "Saratoga_Whidbey"),
]


def clip_mask(AOI,AOI_name,
              orthoDir, 
              homeDir): 
    """
    Clips orthomosaic GeoTIFF tiles to mask shapefiles and calculates BNDVI for each clipped area.

    Parameters:
        orthoDir (str): Directory path for ortho tiles.
        AOI_name (str): Name of the Area of Interest, used to construct file paths.
        homeDir (str): Base directory for project files.
        AOI (str): 3 digit code for aoi, used to construct file paths.

    Outputs:
        - Clipped images: <homeDir>/Clipped_imagery/<AOI>/clipped_image_tiles/image/
        - BNDVI rasters: <homeDir>/Clipped_imagery/<AOI>/clipped_image_tiles/BNDVI/

    Notes:
        - Requires ArcPy and Image Analyst extension.
        - GeoTIFF imagery stored under: <orthoDir>/<AOI_name>/Orthophotography Data/GeoTIFF
        - Mask shapefiles stored under: <homeDir>/Masked_layers/<AOI>, can have any name
    """

    import arcpy
    from arcpy import ia
    import os
    # set path to working directory containing orthomosaic GeoTIFF tiles (e.g., SW_360.tif")
    workingDir = f"{orthoDir}/{AOI_name}/Orthophotography Data/GeoTIFF"
    # set path to directory containing mask shapefiles (e.g., "SW_masks_tc.shp")
    clipDir = f"{homeDir}/Masked_layers/{AOI}"
    # set path for output files
    outDir = f"{homeDir}/Clipped_imagery/{AOI}/clipped_image_tiles"
    outGDB = f"{homeDir}/Clipped_imagery/{AOI}"

    os.makedirs(outDir, exist_ok=True)
    os.makedirs(f"{outDir}/image", exist_ok=True)
    os.makedirs(f"{outDir}/BNDVI", exist_ok=True)

    # set workspace to mask directory, create list of mask shapefiles
    arcpy.env.workspace = f"{clipDir}"
    masks = arcpy.ListFeatureClasses()

    # set workspace to raster directory for rest of script, create list of rasters
    arcpy.env.workspace = f"{workingDir}"
    rasters = arcpy.ListRasters()

    # loop through image (GeoTiff) tiles and masks (shp files), clip imagery to masks,
    # run spectral index on those clips, and save clipped index rasters to output directory
    print("Looping through GeoTiff tiles & masks, clip imagery, run spectral index, save rasters...")
    for raster in rasters:
        if ".tif" in raster.lower():
            # create raster extent object
            rasterDesc = arcpy.Describe(raster)
            rasterExt = rasterDesc.extent
            # set environments for tools that honor them
            arcpy.env.outputCoordinateSystem = raster
            arcpy.env.compression = "LZW"
            # start for loop on masks in mask list
            for mask in masks:
                # create full mask path string
                maskLoc = clipDir + "\\" + f"{mask}"
                cursor = arcpy.SearchCursor(maskLoc)
                rowCount = 1
                for row in cursor:
                    rowShp = row.shape
                    if rasterExt.overlaps(rowShp) or rasterExt.within(rowShp) or rasterExt.contains(rowShp):
                        # create temporary raster object of clipped imagery
                        maskClip = ia.Clip(raster, row.shape)
                        # # optional: save clipped imagery as well as index result below
                        clipOutLoc = os.path.join(outDir, "image", "{}_{}_{}_image.tif".format(raster[:-4], mask[-12:-4], rowCount))
                        if not os.path.exists(clipOutLoc):
                            arcpy.CopyRaster_management(maskClip, clipOutLoc) # may want to add "nodata_value="0"" here at some point but dont want to break it now
                        ##################################################################################################
                        # set paths and names for clipped imagery index outputs, run Band Arithmetic to calculate indices,
                        # and use Copy Raster to save results to output paths
                        # note: Copy Raster honors LZW compression environment above, basic "NDVI.save()" etc., does not
                        ##################################################################################################
                        BNDVIout = os.path.join(outDir, "BNDVI", "{}_{}_{}_BNDVI.tif".format(raster[:-4], mask[-12:-4], rowCount))
                        if not os.path.exists(BNDVIout):
                            BNDVI = arcpy.sa.BandArithmetic(maskClip, "4 3", 1)
                            arcpy.CopyRaster_management(BNDVI, BNDVIout)
                        rowCount += 1

    # create geodatabase and mosaic dataset in gdb output directory location
    print("Creating new gdb...")
    gdbName = f"{AOI}_masked_index_results.gdb"
    arcpy.management.CreateFileGDB(outGDB, gdbName)
    gdbFullPth = outGDB + "\\" + gdbName
    mosaicNameimage = f"{AOI}_image_masked_index_mosaic"
    mosaicNameBNDVI = f"{AOI}_BNDVI_masked_index_mosaic"
    # coordinate systems: NAD83 HARN WA StatePlane South - 2927 (US Ft)
    cordSys = arcpy.SpatialReference(2927)
    print("Creating mosaic datasets...")
    arcpy.management.CreateMosaicDataset(gdbFullPth, mosaicNameimage, cordSys)
    mosaicimageFullPth = gdbFullPth + "\\" + mosaicNameimage
    arcpy.management.CreateMosaicDataset(gdbFullPth, mosaicNameBNDVI, cordSys)
    mosaicBNDVIFullPth = gdbFullPth + "\\" + mosaicNameBNDVI

    # add clipped index rasters in outDir to mosaic, create overviews, and calculate statistics
    print("Add rasters to image mosaic dataset...")
    arcpy.management.AddRastersToMosaicDataset(mosaicimageFullPth, "Raster Dataset", outDir + "\\" + "image", update_overviews="UPDATE_OVERVIEWS")
    print("Calculate statistics for image mosaic dataset...")
    arcpy.management.CalculateStatistics(mosaicimageFullPth, ignore_values = 0) # if this function isn't working, disable calculate statistics

    print("Add rasters to BNDVI mosaic dataset...")
    arcpy.management.AddRastersToMosaicDataset(mosaicBNDVIFullPth, "Raster Dataset", outDir + "\\" + "BNDVI", update_overviews="UPDATE_OVERVIEWS")
    print("Calculate statistics for BNDVI mosaic dataset...")
    arcpy.management.CalculateStatistics(mosaicBNDVIFullPth) # if this function isn't working, disable calculate statistics

    print("Script complete")

def segment_BNDVI(AOI,homeDir): 
    """
    Segments a BNDVI raster using ArcPy's Segment Mean Shift algorithm.

    - Loads a BNDVI mosaic from the project geodatabase.
    - Applies segmentation with specified spectral/spatial detail and minimum segment size.
    - Saves the output raster as a GeoTIFF to: <homeDir>/Segmented_BNDVI/<AOI>/

    Parameters:
        AOI (str): code, used to construct file paths
        homeDir(str): Project root directory.

    Notes:
        - Uses 75% of CPU cores.
        - Requires ArcPy with the Spatial Analyst extension.
    """
    import arcpy
    import os
    # Use 75% of the cores on the machine
    arcpy.env.parallelProcessingFactor = "75%"
    arcpy.env.overwriteOutput = True
    from arcpy import CheckOutExtension # Check out a Spatial Analyst license
    CheckOutExtension("Spatial")    
    from arcpy.sa import SegmentMeanShift
    # Set details for segmentation
    spectralDetail = 20 # [1-20], greater = higher discrimination e.g. btw species
    spatialDetail = 20 # [1-20], greater = better for smaller/clustered together things
    minSeg = 2 # related to minimum mapping unit, units = pixels, 2 = 30cm
    maxSeg = None # optional # related to minimum mapping unit, units = pixels, prevents artifacts due to large segments
    inRaster = f"{homeDir}/Clipped_imagery/{AOI}/{AOI}_masked_index_results.gdb/{AOI}_BNDVI_masked_index_mosaic"
    print(inRaster)
    # Create temporary raster for smoother processing
    tempRaster = arcpy.management.CopyRaster(in_raster=inRaster, out_rasterdataset=arcpy.env.scratchWorkspace + f"/bndvi_copy.tif")
    print(tempRaster)
    # Set out directory
    outDir = f"{homeDir}/Segmented_BNDVI/{AOI}"
    os.makedirs(outDir, exist_ok=True)
    ### Segment imagery
    print("Now segmenting", AOI, "(BNDVI)...", sep=" ")
    # SegmentMeanShift(in_raster, {spectral_detail}, {spatial_detail}, {min_segment_size}, {band_indexes}, {max_segment_size})
    segRaster = SegmentMeanShift(tempRaster, spectral_detail=spectralDetail, spatial_detail=spatialDetail, 
                                 min_segment_size=minSeg, max_segment_size=maxSeg) 
    # Save segmented raster
    print("Saving segmented raster...")
    segRaster.save(outDir + "/" + AOI + "_BNDVI_segmented.tif")
    print("BNDVI segmentation of", AOI, "complete!",sep=" ")

def extract_BNDVISegRaster(AOI,homeDir): 
    """ 
    Extracts a segmented BNDVI raster by masking it with the corresponding mosaic dataset for a given Area of Interest (AOI).

    Parameters:
        AOI (str): The name of the Area of Interest used to locate input and output files.
        homeDir (str, optional): Base directory containing input data and where output will be saved. Defaults to a preset path.

    Notes:
        - Requires an active ArcPy environment with Spatial Analyst extension.
        - Overwrites existing outputs with the same name.
        - Saves the extracted raster as '<AOI>_BNDVI_segmented_clip.tif' in the segmented BNDVI directory.
    """
    import arcpy
    import os
    from arcpy import CheckOutExtension # Check out a Spatial Analyst license
    arcpy.env.overwriteOutput = True
    CheckOutExtension("Spatial")    
    inRaster=f"{homeDir}/Segmented_BNDVI/{AOI}/{AOI}_BNDVI_segmented.tif"
    inMaskData=f"{homeDir}/Clipped_imagery/{AOI}/{AOI}_masked_index_results.gdb/{AOI}_image_masked_index_mosaic"
    print("inRaster", inRaster)
    print("inMaskData", inMaskData)
    arcpy.management.SetMosaicDatasetProperties(inMaskData,mosaic_operator="MAX")
    outDir = f"{homeDir}/Segmented_BNDVI/{AOI}"
    os.makedirs(outDir, exist_ok=True)
    print("Extracting by mask...")
    # ExtractByMask(in_raster, in_mask_data, {extraction_area}, {analysis_extent})
    out_raster = arcpy.sa.ExtractByMask(in_raster=inRaster, 
                                        in_mask_data=inMaskData)
    print("Saving extracted raster...")
    out_raster.save(outDir + "/" + AOI + "_BNDVI_segmented_clip.tif")
    print("Extraction of", AOI, "raster complete!",sep=" ")

def cluster(AOI,homeDir,minSamplesPerCluster=20): 
    """
    Performs iso-cluster classification on imagery using ArcPy.

    Parameters:
        AOI (str): Area of Interest name for file paths.
        homeDir (str, optional): Base directory for data. Defaults to a preset path.
        minSamplesPerCluster (int, optional): Minimum samples per cluster. Defaults to 20.

    Outputs:
        Saves classified raster to '<homeDir>/Classified_Rasters/<AOI>/'.

    Notes: 
        - Requires Image Analyst extension 
    """
    import arcpy
    import os
    # Use 75% of the cores on the machine
    arcpy.env.parallelProcessingFactor = "75%"
    arcpy.env.overwriteOutput = True
    from arcpy import CheckOutExtension
    CheckOutExtension("ImageAnalyst")
    CheckOutExtension("Spatial")
    inRaster=f"{homeDir}/Clipped_imagery/{AOI}/{AOI}_masked_index_results.gdb/{AOI}_image_masked_index_mosaic"
    arcpy.management.SetMosaicDatasetProperties(inRaster,mosaic_operator="MAX")
    BNDVIRaster=f"{homeDir}/Segmented_BNDVI/{AOI}/{AOI}_BNDVI_segmented_clip.tif"
    outDir = f"{homeDir}/Classified_Rasters/{AOI}"
    ClassifierDefinition=f"{homeDir}/Clustered_imagery/{AOI}_image_masked_index_mosaic.ecd"

    os.makedirs(outDir, exist_ok=True) # Creates directory if it doesn't exist
    os.makedirs(f"{homeDir}/Clustered_imagery", exist_ok=True) # Creates directory if it doesn't exist

    print("inRaster", inRaster)
    print("BNDVIRaster",BNDVIRaster)
    print("outDir",outDir)
    print("ClassifierDefinition", ClassifierDefinition)

    # Choose which bands to use for Classification - [4,2,3] is NIR-G-B
    print("Creating color composite (NGB bands only)...")
    colorCompositeRaster = arcpy.ia.ExtractBand(inRaster,[4,2,3])
    tmp_raster = os.path.join(outDir, f"{AOI}_color_composite.tif")
    print("Saving colorCompositeRaster...")
    arcpy.CopyRaster_management(colorCompositeRaster, tmp_raster)

    # TrainIsoClusterClassifier(in_raster, max_classes, out_classifier_definition, 
    #       {in_additional_raster}, {max_iterations}, {min_samples_per_cluster}, 
    #       {skip_factor}, {used_attributes}, {max_merge_per_iter}, {max_merge_distance})
    #print("Skip TrainIsoClusterClassifier...")
    print("Running TrainIsoClusterClassifier...")
    arcpy.ia.TrainIsoClusterClassifier(in_raster=tmp_raster, max_classes=10, 
                                       out_classifier_definition=ClassifierDefinition, 
                                       in_additional_raster=BNDVIRaster, 
                                       max_iterations=20, min_samples_per_cluster=minSamplesPerCluster, 
                                       skip_factor=10, 
                                       used_attributes="COLOR;MEAN;STD", 
                                       max_merge_per_iter=5) #, max_merge_distance=0.75
    print("Running ClassifyRaster...")
    ClassifiedRaster=arcpy.ia.ClassifyRaster(in_raster=tmp_raster,
                     in_additional_raster=BNDVIRaster,
                     in_classifier_definition=ClassifierDefinition)
    print("Saving classified raster...")
    ClassifiedRaster.save(outDir + "/" + AOI + "_classified.tif")
    print(AOI + " clustering complete!")

if __name__ == "__main__":
    import logging
    import os
    import arcpy
    import shutil

    # Configure logging once, at the start
    logging.basicConfig(
        filename="overnight_run.log",   # log file name
        filemode="a",                   # <-- "append" mode
        level=logging.INFO,             # capture INFO and above
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Optional: also show logs in console while writing to file
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console.setFormatter(formatter)
    logging.getLogger("").addHandler(console)

    # Run the pipeline
    for AOI, AOI_name in datasets:
        logging.info(f"=== Starting {AOI} ({AOI_name}) ===")
        
        # Set up scratch folder
        scratch = os.path.join(homeDir, "scratch", AOI)
        os.makedirs(scratch, exist_ok=True)
        arcpy.env.workspace = scratch
        arcpy.env.scratchWorkspace = scratch
        
        try:
            # -----------------------------
            # Output paths for skip-check
            # -----------------------------
            clip_mask_out = f"{homeDir}/Clipped_imagery/{AOI}/{AOI}_masked_index_results.gdb/"
            segment_BNDVI_out = f"{homeDir}/Segmented_BNDVI/{AOI}/{AOI}_BNDVI_segmented.tif"
            extract_BNDVISegRaster_out = f"{homeDir}/Segmented_BNDVI/{AOI}/{AOI}_BNDVI_segmented_clip.tif"
            cluster_out = f"{homeDir}/Classified_Rasters/{AOI}/{AOI}_classified.tif"

            # -----------------------------
            # Function 1: clip_mask
            # -----------------------------
            if not os.path.exists(clip_mask_out): 
                clip_mask(AOI,AOI_name,orthoDir,homeDir)
            else:
                logging.info(f"Skipping clip_mask - {AOI} (already exists)")
            
            # -----------------------------
            # Function 2: Segment BNDVI
            # -----------------------------
            if not os.path.exists(segment_BNDVI_out): 
                segment_BNDVI(AOI,homeDir)
            else:
                logging.info(f"Skipping segment_BNDVI - {AOI} (already exists)")
            
            # -----------------------------
            # Function 3: extract segmented BNDVI raster
            # -----------------------------
            if not os.path.exists(extract_BNDVISegRaster_out): 
                extract_BNDVISegRaster(AOI,homeDir)
            else:
                logging.info(f"Skipping extract_BNDVISegRaster - {AOI} (already exists)")
                
            # -----------------------------
            # Function 4: cluster
            # -----------------------------
            if not os.path.exists(cluster_out): 
                cluster(AOI,homeDir)
            else:
                logging.info(f"Skipping cluster - {AOI} (already exists)")

            logging.info(f"✅ {AOI} completed successfully")

        except Exception as e:
            logging.error(f"❌ Error processing {AOI} ({AOI_name}): {e}")
            # Skip the rest of this dataset, continue with next one
            continue # fast-fail per AOI

        finally:
            # -----------------------------
            # Optional: delete scratch folder to save space
            # -----------------------------
            try:
                shutil.rmtree(scratch, ignore_errors=True)  
                logging.info(f"Cleaned up scratch folder for {AOI}")
            except Exception as cleanup_err:
                logging.warning(f"Failed to delete scratch folder for {AOI}: {cleanup_err}")