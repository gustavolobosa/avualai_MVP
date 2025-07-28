const pool = require('../db');

function limpiarEntero(valor) {
    if (!valor && valor !== 0) return null;
    return parseInt(valor.toString().replace(/\./g, '').replace(/\$/g, '')) || null;
}

async function insertarPredio(data) {
    const {
        clave_predio,
        anio,
        semestre,
        indicador_de_aseo,
        direccion_predial,
        manzana_actual,
        predio_actual,
        cod_serie,
        cuota_trimestral,
        avaluo_tot,
        avaluo_ex,
        anio_termino_ex,
        cod_ubi,
        cod_destino
    } = data;

    const query = `
        INSERT INTO propiedades (
            clave_predio, anio, semestre, indicador_de_aseo, direccion_predial,
            manzana_actual, predio_actual, cod_serie, cuota_trimestral,
            avaluo_tot, avaluo_ex, anio_termino_ex, cod_ubi, cod_destino
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7, $8, $9,
            $10, $11, $12, $13, $14
        )
        ON CONFLICT (clave_predio) DO UPDATE SET
            anio = EXCLUDED.anio,
            semestre = EXCLUDED.semestre,
            indicador_de_aseo = EXCLUDED.indicador_de_aseo,
            direccion_predial = EXCLUDED.direccion_predial,
            manzana_actual = EXCLUDED.manzana_actual,
            predio_actual = EXCLUDED.predio_actual,
            cod_serie = EXCLUDED.cod_serie,
            cuota_trimestral = EXCLUDED.cuota_trimestral,
            avaluo_tot = EXCLUDED.avaluo_tot,
            avaluo_ex = EXCLUDED.avaluo_ex,
            anio_termino_ex = EXCLUDED.anio_termino_ex,
            cod_ubi = EXCLUDED.cod_ubi,
            cod_destino = EXCLUDED.cod_destino
        RETURNING *;
    `;

    const values = [
        clave_predio,
        anio,
        semestre,
        indicador_de_aseo,
        direccion_predial,
        manzana_actual,
        predio_actual,
        cod_serie,
        cuota_trimestral,
        avaluo_tot,
        avaluo_ex,
        anio_termino_ex,
        cod_ubi,
        cod_destino
    ];

    const result = await pool.query(query, values);
    return result.rows[0];
}

async function obtenerPredios() {
    const result = await pool.query('SELECT * FROM propiedades LIMIT 100');
    return result.rows;
}

module.exports = {
    insertarPredio,
    obtenerPredios
};
