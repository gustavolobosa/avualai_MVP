CREATE TABLE propiedades (
    clave_predio VARCHAR PRIMARY KEY,
    anio INT,
    semestre INT,
    indicador_de_aseo VARCHAR(5),
    direccion_predial TEXT,
    manzana_actual INT,
    predio_actual INT,
    comuna_actual VARCHAR REFERENCES comunas(cod_comuna),
    cod_serie VARCHAR(5),
    cuota_trimestral BIGINT,
    avaluo_tot BIGINT,
    avaluo_ex BIGINT,
    anio_termino_ex INT,
    cod_ubi VARCHAR(5),
    cod_destino VARCHAR(5)
);

CREATE TABLE info_rol_construccion (
    id SERIAL PRIMARY KEY,
    clave_predio VARCHAR REFERENCES propiedades(clave_predio),
    correlativo_linea_constru INT,
    cod_material VARCHAR REFERENCES materiales(cod_material),
    cod_calidad VARCHAR REFERENCES calidad(cod_calidad),
    anio_constru INT,
    sup_constru INT,
    cod_condicion_especial VARCHAR REFERENCES condicion_especial(cod_condicion_especial) NULL
);

CREATE TABLE info_rol (
    clave_predio VARCHAR PRIMARY KEY REFERENCES propiedades(clave_predio),
    avaluo_fiscal_total BIGINT,
    avaluo_exento BIGINT,
    contribuciones_semana_con_aseo BIGINT,
    superficie_total INT,
    clave_predio_bien_comun_1 VARCHAR REFERENCES propiedades(clave_predio) ON DELETE SET NULL,
    clave_predio_bien_comun_2 VARCHAR REFERENCES propiedades(clave_predio) ON DELETE SET NULL
);


CREATE TABLE comunas (
    cod_comuna VARCHAR PRIMARY KEY,
    nombre_comuna TEXT,
    cod_tesoreria VARCHAR
);

CREATE TABLE calidad (
    cod_calidad VARCHAR PRIMARY KEY,
    descripcion TEXT
);

CREATE TABLE condicion_especial (
    cod_condicion_especial VARCHAR PRIMARY KEY,
    descripcion TEXT
);

CREATE TABLE destinos (
    cod_destino VARCHAR PRIMARY KEY,
    descripcion TEXT
);

CREATE TABLE materiales (
    cod_material VARCHAR PRIMARY KEY,
    descripcion TEXT
);


