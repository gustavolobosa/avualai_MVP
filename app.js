const express = require('express');
const app = express();
const path = require('path');

const propiedadesRoutes = require('./routes/propiedades'); // ← aquí va primero
const infoConstruccionRoutes = require('./routes/info_construccion');
const infoRolRoutes = require('./routes/info_rol');


app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(express.json());
app.use('/propiedades', propiedadesRoutes); // ← ahora sí puedes usarlo
app.use('/info-construccion', infoConstruccionRoutes);
app.use('/info-rol', infoRolRoutes);


// Middleware to parse form data
app.use(express.urlencoded({ extended: true }));

// Serve static files
app.use(express.static('public'));

// Import your scrapers
const runScrapers = require('./scrapers/main');

// Form submission endpoint
app.post('/run-scrapers', (req, res) => {
    const { comuna, region, direccion, numero } = req.body;

    runScrapers({ comuna, region, direccion, numero })
        .then(result => {
            res.render('result', { result });
        })
        .catch(error => {
            res.status(500).send(`Error: ${error.message}`);
        });
});

// Start server
const PORT = 3000;
app.listen(PORT, () => {
    console.log(`Server running at http://localhost:${PORT}`);
});
