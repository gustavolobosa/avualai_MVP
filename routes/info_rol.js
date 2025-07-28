const express = require('express');
const router = express.Router();
const { insertarInfoRol, obtenerInfoRol } = require('../models/info_rol');

router.get('/', async (req, res) => {
    const info = await obtenerInfoRol();
    res.json(info);
});

router.post('/', async (req, res) => {
    try {
        const nueva = await insertarInfoRol(req.body);
        res.status(201).json(nueva);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Error al insertar info_rol' });
    }
});

module.exports = router;
