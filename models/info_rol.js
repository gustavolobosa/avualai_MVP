const pool = require('../db');

async function insertarInfoRol(data) {
    const {
        avaluo_fiscal_total,
        contribuciones_semana_con_aseo,
        avaluo_exento,
        superficie_total,
        clave_predio_bien_comun_1,
        clave_predio_bien_comun_2
    } = data;

    const query = `
        INSERT INTO info_rol (
            avaluo_fiscal_total,
            contribuciones_semana_con_aseo,
            avaluo_exento,
            superficie_total,
            clave_predio_bien_comun_1,
            clave_predio_bien_comun_2
        ) VALUES ($1, $2, $3, $4, $5)
        RETURNING *;
    `;

    const values = [
        avaluo_fiscal_total,
        contribuciones_semana_con_aseo,
        avaluo_exento,
        superficie_total,
        clave_predio_bien_comun_1,
        clave_predio_bien_comun_2
    ];

    const result = await pool.query(query, values);
    return result.rows[0];
}

async function obtenerInfoRol() {
    const result = await pool.query('SELECT * FROM info_rol');
    return result.rows;
}

module.exports = {
    insertarInfoRol,
    obtenerInfoRol
};
