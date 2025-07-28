const express = require('express');
const router = express.Router();
const { insertarPropiedad, obtenerPropiedades } = require('../models/propiedades');

// GET /propiedades
router.get('/', async (req, res) => {
    const propiedades = await obtenerPropiedades();
    res.json(propiedades);
});


module.exports = router;
