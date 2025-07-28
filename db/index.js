const { Pool } = require('pg');
require('dotenv').config();

const pool = new Pool(); // lee desde .env automáticamente
module.exports = pool;
