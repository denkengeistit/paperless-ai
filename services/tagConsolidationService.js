const stringSimilarity = require('string-similarity');
const paperlessService = require('./paperlessService');

class TagConsolidationService {
  constructor(paperlessService) {
    this.paperlessService = paperlessService;
    this.similarityThreshold = 0.8; // Configurable threshold for tag similarity
  }

  /**
   * Analyzes tags and suggests consolidations based on similarity
   * @returns {Promise<Object>} Object containing consolidation suggestions
   */
  async analyzeTags() {
    try {
      // Get all tags from Paperless
      const response = await this.paperlessService.client.get('/tags/');
      const tags = response.data.results;

      // Group similar tags
      const similarGroups = this.findSimilarTags(tags);
      
      // Analyze tag usage
      const usageAnalysis = await this.analyzeTagUsage(tags);

      // Generate consolidation suggestions
      const suggestions = this.generateSuggestions(similarGroups, usageAnalysis);

      return {
        similarGroups,
        usageAnalysis,
        suggestions
      };
    } catch (error) {
      console.error('[ERROR] analyzing tags:', error.message);
      throw error;
    }
  }

  /**
   * Finds groups of similar tags using string similarity
   * @param {Array} tags Array of tag objects from Paperless
   * @returns {Array} Array of tag groups
   */
  findSimilarTags(tags) {
    const groups = [];
    const processed = new Set();

    for (const tag of tags) {
      if (processed.has(tag.id)) continue;

      const group = [tag];
      processed.add(tag.id);

      // Compare with other tags
      for (const otherTag of tags) {
        if (processed.has(otherTag.id)) continue;

        const similarity = stringSimilarity.compareTwoStrings(
          tag.name.toLowerCase(),
          otherTag.name.toLowerCase()
        );

        if (similarity >= this.similarityThreshold) {
          group.push(otherTag);
          processed.add(otherTag.id);
        }
      }

      if (group.length > 1) {
        groups.push(group);
      }
    }

    return groups;
  }

  /**
   * Analyzes how tags are used across documents
   * @param {Array} tags Array of tag objects
   * @returns {Promise<Object>} Usage statistics for each tag
   */
  async analyzeTagUsage(tags) {
    const usage = {};

    for (const tag of tags) {
      try {
        // Get documents using this tag
        const response = await this.paperlessService.client.get('/documents/', {
          params: {
            tags__id: tag.id,
            page_size: 1
          }
        });

        usage[tag.id] = {
          tag: tag,
          documentCount: response.data.count,
          lastUsed: null
        };

        // Get the most recent document using this tag
        if (response.data.count > 0) {
          const recentResponse = await this.paperlessService.client.get('/documents/', {
            params: {
              tags__id: tag.id,
              ordering: '-created',
              page_size: 1
            }
          });

          if (recentResponse.data.results.length > 0) {
            usage[tag.id].lastUsed = recentResponse.data.results[0].created;
          }
        }
      } catch (error) {
        console.error(`[ERROR] analyzing usage for tag ${tag.name}:`, error.message);
        usage[tag.id] = {
          tag: tag,
          documentCount: 0,
          lastUsed: null,
          error: error.message
        };
      }
    }

    return usage;
  }

  /**
   * Generates consolidation suggestions based on similar tags and usage
   * @param {Array} similarGroups Groups of similar tags
   * @param {Object} usageAnalysis Tag usage statistics
   * @returns {Array} Array of consolidation suggestions
   */
  generateSuggestions(similarGroups, usageAnalysis) {
    const suggestions = [];

    for (const group of similarGroups) {
      // Sort group by usage (most used first)
      group.sort((a, b) => {
        const usageA = usageAnalysis[a.id]?.documentCount || 0;
        const usageB = usageAnalysis[b.id]?.documentCount || 0;
        return usageB - usageA;
      });

      const primaryTag = group[0];
      const secondaryTags = group.slice(1);

      suggestions.push({
        primaryTag: {
          id: primaryTag.id,
          name: primaryTag.name,
          documentCount: usageAnalysis[primaryTag.id]?.documentCount || 0
        },
        tagsToConsolidate: secondaryTags.map(tag => ({
          id: tag.id,
          name: tag.name,
          documentCount: usageAnalysis[tag.id]?.documentCount || 0
        })),
        reason: 'Similar names',
        confidence: this.calculateConfidence(group, usageAnalysis)
      });
    }

    return suggestions;
  }

  /**
   * Calculates confidence score for a consolidation suggestion
   * @param {Array} tagGroup Group of similar tags
   * @param {Object} usageAnalysis Tag usage statistics
   * @returns {number} Confidence score between 0 and 1
   */
  calculateConfidence(tagGroup, usageAnalysis) {
    if (tagGroup.length < 2) return 0;

    // Calculate name similarity scores
    const similarityScores = [];
    for (let i = 0; i < tagGroup.length; i++) {
      for (let j = i + 1; j < tagGroup.length; j++) {
        const similarity = stringSimilarity.compareTwoStrings(
          tagGroup[i].name.toLowerCase(),
          tagGroup[j].name.toLowerCase()
        );
        similarityScores.push(similarity);
      }
    }

    // Calculate usage ratio
    const totalUsage = tagGroup.reduce((sum, tag) => 
      sum + (usageAnalysis[tag.id]?.documentCount || 0), 0);
    const primaryUsage = usageAnalysis[tagGroup[0].id]?.documentCount || 0;
    const usageRatio = totalUsage > 0 ? primaryUsage / totalUsage : 0;

    // Combine scores
    const avgSimilarity = similarityScores.reduce((a, b) => a + b, 0) / similarityScores.length;
    return (avgSimilarity * 0.7 + usageRatio * 0.3);
  }

  /**
   * Implements a consolidation suggestion
   * @param {Object} suggestion Consolidation suggestion
   * @returns {Promise<Object>} Result of the consolidation
   */
  async implementConsolidation(suggestion) {
    const results = {
      success: true,
      errors: [],
      documentsUpdated: 0
    };

    try {
      // For each document using secondary tags, add the primary tag
      for (const secondaryTag of suggestion.tagsToConsolidate) {
        const response = await this.paperlessService.client.get('/documents/', {
          params: {
            tags__id: secondaryTag.id,
            page_size: 100
          }
        });

        for (const document of response.data.results) {
          try {
            // Get current tags
            const currentTags = document.tags || [];
            
            // Add primary tag if not present
            if (!currentTags.includes(suggestion.primaryTag.id)) {
              const updatedTags = [...currentTags, suggestion.primaryTag.id];
              
              // Update document
              await this.paperlessService.client.patch(`/documents/${document.id}/`, {
                tags: updatedTags
              });
              
              results.documentsUpdated++;
            }
          } catch (error) {
            results.errors.push({
              documentId: document.id,
              error: error.message
            });
          }
        }
      }

      // Delete secondary tags if all documents were updated successfully
      if (results.errors.length === 0) {
        for (const secondaryTag of suggestion.tagsToConsolidate) {
          try {
            await this.paperlessService.client.delete(`/tags/${secondaryTag.id}/`);
          } catch (error) {
            results.errors.push({
              tagId: secondaryTag.id,
              error: error.message
            });
          }
        }
      }

    } catch (error) {
      results.success = false;
      results.errors.push({
        error: error.message
      });
    }

    return results;
  }
}

module.exports = { TagConsolidationService }; 