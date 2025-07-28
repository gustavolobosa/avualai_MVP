const express = require('express');
const router = express.Router();
const {
    insertarConstruccion,
    obtenerConstrucciones
} = require('../models/info_construccion');

// GET /info-construccion
router.get('/', async (req, res) => {
    const construcciones = await obtenerConstrucciones();
    res.json(construcciones);
});


module.exports = router;
