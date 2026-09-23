// frontend/compare.js
// Compare logic - can be called from chat view when agent triggers comparison

import { API } from './api.js';

async function compareDocuments(docId1, docId2, threshold = 0.7) {
    try {
        const response = await API.compareDocuments(docId1, docId2, threshold);

        if (response.ok) {
            return await response.json();
        } else {
            const error = await response.json();
            throw new Error(error.detail || 'Comparison failed');
        }
    } catch (err) {
        throw new Error(err.message || 'Network error during comparison');
    }
}

function formatCompareResult(result) {
    if (!result || !result.similar_clauses) {
        return 'No comparison results available.';
    }

    const { similar_clauses, total_comparisons, document_1_filename, document_2_filename, comparison_time_ms } = result;

    let output = `**Comparison: ${document_1_filename} vs ${document_2_filename}**\n`;
    output += `Total comparisons: ${total_comparisons} | Time: ${comparison_time_ms}ms\n\n`;

    if (similar_clauses.length === 0) {
        output += 'No similar clauses found above the threshold.';
        return output;
    }

    output += `**Found ${similar_clauses.length} similar clause(s):**\n\n`;

    similar_clauses.forEach((clause, i) => {
        output += `${i + 1}. **Similarity: ${(clause.similarity_score * 100).toFixed(1)}%**\n`;
        output += `   Doc 1 (p.${clause.document_1_page}): "${clause.clause_1.substring(0, 100)}..."\n`;
        output += `   Doc 2 (p.${clause.document_2_page}): "${clause.clause_2.substring(0, 100)}..."\n\n`;
    });

    return output;
}

export { compareDocuments, formatCompareResult };