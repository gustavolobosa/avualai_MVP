const pool = require('../db');

async function insertarConstruccion(data) {
    const {
        clave_predio,
        correlativo_linea_constru,
        cod_material,
        cod_calidad,
        año_constru,
        sup_constru,
        cod_condicion_especial
    } = data;

    const query = `
        INSERT INTO info_rol_construccion (
            clave_predio, correlativo_linea_constru, cod_material, cod_calidad,
            año_constru, sup_constru, cod_condicion_especial
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (clave_predio) DO UPDATE SET
            correlativo_linea_constru = EXCLUDED.correlativo_linea_constru,
            cod_material = EXCLUDED.cod_material,
            cod_calidad = EXCLUDED.cod_calidad,
            año_constru = EXCLUDED.año_constru,
            sup_constru = EXCLUDED.sup_constru,
            cod_condicion_especial = EXCLUDED.cod_condicion_especial
        RETURNING *;
    `;

    const values = [
        clave_predio,
        correlativo_linea_constru,
        cod_material,
        cod_calidad,
        año_constru,
        sup_constru,
        cod_condicion_especial
    ];

    const result = await pool.query(query, values);
    return result.rows[0];
}

async function obtenerConstrucciones() {
    const result = await pool.query('SELECT * FROM info_rol_construccion');
    return result.rows;
}

module.exports = {
    insertarConstruccion,
    obtenerConstrucciones
};
