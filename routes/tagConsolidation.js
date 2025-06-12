const express = require('express');
const router = express.Router();
const { TagConsolidationService } = require('../services/tagConsolidationService');
const paperlessService = require('../services/paperlessService');

// Initialize tag consolidation service
const tagConsolidationService = new TagConsolidationService(paperlessService);

/**
 * @swagger
 * /api/tags/analyze:
 *   get:
 *     summary: Analyze tags and get consolidation suggestions
 *     tags: [Tags]
 *     responses:
 *       200:
 *         description: Tag analysis results
 */
router.get('/analyze', async (req, res) => {
  try {
    const analysis = await tagConsolidationService.analyzeTags();
    res.json(analysis);
  } catch (error) {
    console.error('[ERROR] analyzing tags:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * @swagger
 * /api/tags/consolidate:
 *   post:
 *     summary: Implement a tag consolidation suggestion
 *     tags: [Tags]
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               primaryTag:
 *                 type: object
 *               tagsToConsolidate:
 *                 type: array
 */
router.post('/consolidate', async (req, res) => {
  try {
    const result = await tagConsolidationService.implementConsolidation(req.body);
    res.json(result);
  } catch (error) {
    console.error('[ERROR] consolidating tags:', error);
    res.status(500).json({ error: error.message });
  }
});

module.exports = router; 