#Importar Modulos
import arcpy
import os
#Establecer Variables Locales
GDB = r"\Proyecto_SIG.gdb"
school = r"\Proyecto_SIG.gdb\Insumos\IED_Rural"
vereda = r"\Proyecto_SIG.gdb\Insumos\Vereda"
road = r"\Proyecto_SIG.gdb\Insumos\Via"
dataset_insumos = GDB + r"\Insumos"
network_dataset = dataset_insumos + r"\AnalisisVia"
location_folder = os.getcwd()
def ScriptTool(param0, param1):
    
    set_workespace(GDB)
    
    dataset_products_intermediate = create_Dataset("Productos_intermedios")
    dataset_products = create_Dataset("Productos")
    
    create_NetworkDataSet()
    influence_Area = create_Influence_Area(dataset_products_intermediate, dataset_products)
    students = create_ramdom_students(dataset_products_intermediate, influence_Area)
    final_road = seleccion(dataset_products, influence_Area, students)
    resultadosFinales(final_road)
    return
def set_workespace(workspace):
    arcpy.env.workspace = workspace
    arcpy.env.overwriteOutput = True
    
def create_Dataset(nombre):
    spatial_reference = obtenerReferenciaEspacial()
    arcpy.management.CreateFeatureDataset(GDB, nombre, spatial_reference)
    return GDB + f"\{nombre}"
def create_NetworkDataSet():
    if arcpy.Exists(network_dataset):
        return 0 
    else:
        arcpy.na.CreateNetworkDataset(dataset_insumos, "AnalisisVia", "Via", "NO_ELEVATION")
        arcpy.na.BuildNetwork(network_dataset)
        
def create_Influence_Area(dataset_1, dataset_2):
    spatial_reference = obtenerReferenciaEspacial()
    set_workespace(dataset_1)
    
    influence_area = arcpy.analysis.CreateThiessenPolygons(school, "Area_Influencia", "ALL")
    influence_area_final = arcpy.analysis.Clip(influence_area, vereda, "Area_Influencia_Final")
    
    road_area = arcpy.analysis.Intersect([road, influence_area_final], "ViasxArea")
    arcpy.management.AddField(road_area,"Long_Vial","DOUBLE",None,None,None,"Long_Vial")
    arcpy.management.CalculateGeometryAttributes(road_area, "Long_Vial LENGTH", "KILOMETERS")
    
    set_workespace(GDB)
    tabla = arcpy.analysis.Statistics(road_area, "Tabla_ViasxArea", "Long_Vial SUM", "Input_FID")
    set_workespace(dataset_2)
    table_join = arcpy.management.AddJoin(influence_area_final,"Input_FID", tabla, "Input_FID")
    road_density = arcpy.management.CopyFeatures(table_join,"Densidad_Vial")
    arcpy.management.AddField(road_density,"Area","DOUBLE",None,None,None,"Area(km)")
    
    arcpy.management.CalculateGeometryAttributes(road_density, "Area AREA", "", "SQUARE_KILOMETERS")
    arcpy.management.AddField(road_density,"Dens_Vial","DOUBLE",None,None,None,"Dens_Vial")
    arcpy.management.CalculateField(road_density, "Dens_Vial", "!Tabla_ViasxArea_SUM_Long_Vial!/!Area!")
    
    return influence_area_final
    
    
def create_ramdom_students(dataset, poligono):
    students = arcpy.management.CreateRandomPoints(dataset, "estudiantes", poligono, "", "INSCRITOS")
    set_workespace(dataset)
    intersectar = [students, poligono]
    studentsxIE = arcpy.analysis.Intersect(intersectar, "Estudiantes_finales")
    arcpy.management.DeleteField(studentsxIE, "INSCRITOS")
    
    return studentsxIE
    
def seleccion(dataset_1, poligono, estudiantes):
    
    with arcpy.da.SearchCursor(poligono, ["OID@","NOMBRE","CODIGO"]) as cursor:
        for row in cursor:
            output_layer_file = os.path.join(location_folder + f"\Layer", "Ruta_Estudiantes" + f"_{row[0]}.lyrx")
            set_workespace(GDB)
            
            result_object = arcpy.na.MakeClosestFacilityAnalysisLayer(network_dataset, "Ruta_Estudiantes" + f"{row[0]}","" ,"TO_FACILITIES", None, 12)
            analysis_layer = result_object.getOutput(0)
            sublayers = arcpy.na.GetNAClassNames(analysis_layer)
        
            facilities_layer = sublayers["Facilities"]
            incidents_layer = sublayers["Incidents"]
            
            selected_Influence_Area = arcpy.analysis.Select(poligono, "Area_Seleccionada", f"OBJECTID = {row[0]}")
                   
            school_intersect = [school,selected_Influence_Area]
            student_intersect = [estudiantes,selected_Influence_Area]
            selected_school = arcpy.analysis.Intersect(school_intersect, "Colegio_seleccionado")
            selected_students = arcpy.analysis.Intersect(student_intersect, "Vias_seleccionadas")
                    
            arcpy.na.AddLocations(analysis_layer, facilities_layer, selected_students)
                    
            field_mappings = arcpy.na.NAClassFieldMappings(analysis_layer, incidents_layer)
            field_mappings["Name"].mappedFieldName = "NOM"
            
            arcpy.na.AddLocations(analysis_layer, incidents_layer, selected_school, field_mappings, "")
            
            arcpy.na.Solve(analysis_layer)
                    
            analysis_layer.saveACopy(output_layer_file)
 
            arcpy.na.CopyTraversedSourceFeatures(analysis_layer, GDB, "bordes", "cruces", "giros")
            bordes = GDB + r"\bordes"
            cruces = GDB + r"\cruces"
            giros = GDB + r"\giros"
                    
            if row[0] == 1:
                set_workespace(dataset_1)
                final_road = arcpy.analysis.Intersect([road, bordes], "Ruta")
                
                arcpy.management.AddField(final_road,"CODIGO_IE","TEXT",None,None,None,"CODIGO_IE")
                arcpy.management.CalculateField(final_road, "CODIGO_IE",f"'{row[2]}'")
                
            else:
                selected_road = arcpy.analysis.Intersect([road, bordes], "Via_Seleccionada")
                arcpy.management.AddField(selected_road,"CODIGO_IE","TEXT",None,None,None,"CODIGO_IE")
                arcpy.management.CalculateField(selected_road, "CODIGO_IE",f"'{row[2]}'")
                arcpy.management.Append(selected_road, final_road)
            
            layer = arcpy.mp.LayerFile(location_folder + f"\Layer\Ruta_Estudiantes_{row[0]}.lyrx")
            
            for l in layer.listLayers():
                if l.name == "Incidentes":
                    arcpy.management.AddField(l.dataSource,"NOMBRE_IE","TEXT",None,None,None,"NOMBRE_IE")
                    arcpy.management.CalculateField(l.dataSource, "NOMBRE_IE",f"'{row[1]}'")
        eraser = [selected_Influence_Area, selected_school, selected_students, bordes, cruces, giros, selected_road]
        deleteEntities(eraser)
        
        return final_road
        
    
def resultadosFinales(ruta):
    set_workespace(GDB)
    arcpy.management.AddField(ruta,"Longitud","DOUBLE",None,None,None,"Longitud(km)")
    arcpy.management.CalculateGeometryAttributes(ruta, "Longitud LENGTH", "KILOMETERS")
    arcpy.analysis.Statistics(ruta, "Tipo_vias", "Longitud SUM", "TIPO_VIA")
    
def obtenerReferenciaEspacial():
    dsc = arcpy.Describe(road)
    sr = dsc.spatialReference
    return sr
def deleteEntities(eraser):
    for i in range(len(eraser)):
        arcpy.Delete_management(eraser[i])
  
# This is used to execute code if the file was run but not imported
if __name__ == '__main__':
    # Tool parameter accessed with GetParameter or GetParameterAsText
    param0 = arcpy.GetParameterAsText(0)
    param1 = arcpy.GetParameterAsText(1)
    
    ScriptTool(param0, param1)
    
    # Update derived parameter values using arcpy.SetParameter() or arcpy.SetParameterAsText()
    
    
