# -*- coding: utf-8 -*-
"""abstract_deploy.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/10JA7JnI8N82GW7AYDpwzD5ZB3psKiaeV
"""


import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import base64

# Set page config
st.set_page_config(
    page_title="Thesis Abstract Recommendation System",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .stAlert {
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'recommendations' not in st.session_state:
    st.session_state.recommendations = None

def load_data():
    """Load the required datasets"""
    try:
        # Load scopus data
        scopus_df = pd.read_csv('scopus.csv')
        scopus_filtered = scopus_df[['Author full names', 'Author(s) ID', 'Abstract', 'Author Keywords', 'Index Keywords']]

        # Load FUTA authors data
        futa_authors = pd.read_csv('futa_authors.csv')
        futa_authors = futa_authors.dropna(how='all')

        return scopus_filtered, futa_authors
    except FileNotFoundError as e:
        st.error(f"Required CSV files not found: {e}")
        return None, None



def calculate_similarity(target_abstract, scopus_data):
    """Calculate cosine similarity between target abstract and scopus data"""
    results = []

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i in range(len(scopus_data)):
        progress = (i + 1) / len(scopus_data)
        progress_bar.progress(progress)
        status_text.text(f'Processing paper {i+1}/{len(scopus_data)}')

        vectorizer = TfidfVectorizer(stop_words='english', max_features=5000)

        # Abstract similarity
        try:
            vector_abs = vectorizer.fit_transform([scopus_data['Abstract'].iloc[i], target_abstract])
            similarity_abs = cosine_similarity(vector_abs)[0][1]
        except:
            similarity_abs = 0

        # Author keywords similarity
        try:
            if pd.notna(scopus_data['Author Keywords'].iloc[i]):
                vector_aut = vectorizer.fit_transform([scopus_data['Author Keywords'].iloc[i], target_abstract])
                similarity_aut = cosine_similarity(vector_aut)[0][1]
            else:
                similarity_aut = np.nan
        except:
            similarity_aut = np.nan

        # Index keywords similarity
        try:
            if pd.notna(scopus_data['Index Keywords'].iloc[i]):
                vector_ind = vectorizer.fit_transform([scopus_data['Index Keywords'].iloc[i], target_abstract])
                similarity_ind = cosine_similarity(vector_ind)[0][1]
            else:
                similarity_ind = np.nan
        except:
            similarity_ind = np.nan

        results.append([
            scopus_data['Author full names'].iloc[i],
            scopus_data['Author(s) ID'].iloc[i],
            similarity_abs,
            similarity_aut,
            similarity_ind
        ])

    progress_bar.empty()
    status_text.empty()

    return pd.DataFrame(results, columns=['Authors', 'IDs', 'Score_Abs', 'Score_Author', 'Score_Index'])

def process_author_ids(results_df, futa_authors):
    """Process author IDs and merge with FUTA authors data"""
    author_scores = []

    for i, row in results_df.iterrows():
        if pd.notna(row['IDs']):
            ids = str(row['IDs']).split(';')
            for author_id in ids:
                try:
                    author_scores.append([float(author_id.strip()), np.round(row['Score_Abs'], 3)])
                except ValueError:
                    continue

    author_scores_df = pd.DataFrame(author_scores, columns=['Auth-ID', 'Score'])

    # Merge with FUTA authors
    merged_df = author_scores_df.merge(futa_authors, how='inner', on='Auth-ID')

    return merged_df.sort_values('Score', ascending=False)

def create_visualizations(recommendations_df):
    """Create visualizations for the recommendations"""
    
    # Check if we have data
    if len(recommendations_df) == 0:
        return None, None, None
    
    # Find the correct column names
    name_candidates = ['Name', 'Author', 'Full Name', 'Author Name', 'Authors', 'Author full names']
    name_col = None
    for candidate in name_candidates:
        if candidate in recommendations_df.columns:
            name_col = candidate
            break
    
    # If no standard name column found, use the first string column
    if name_col is None:
        string_cols = recommendations_df.select_dtypes(include=['object']).columns
        if len(string_cols) > 0:
            name_col = string_cols[0]
    
    # If still no name column, create a generic one
    if name_col is None:
        recommendations_df = recommendations_df.copy()
        recommendations_df['Name'] = [f"Author {i+1}" for i in range(len(recommendations_df))]
        name_col = 'Name'
    
    # Ensure Score column exists
    if 'Score' not in recommendations_df.columns:
        print("Warning: 'Score' column not found. Using first numeric column.")
        numeric_cols = recommendations_df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            score_col = numeric_cols[0]
        else:
            return None, None, None
    else:
        score_col = 'Score'

    # Top 20 recommendations bar chart
    top_20 = recommendations_df.head(20).copy()
    
    try:
        fig1 = px.bar(
            top_20,
            x=score_col,
            y=name_col,
            orientation='h',
            title='Top 20 Recommended Internal Examiners',
            labels={score_col: 'Similarity Score', name_col: 'Lecturer Name'},
            color=score_col,
            color_continuous_scale='viridis'
        )
        fig1.update_layout(height=600, yaxis={'categoryorder': 'total ascending'})
    except Exception as e:
        print(f"Error creating bar chart: {e}")
        fig1 = None

    # Score distribution
    try:
        fig2 = px.histogram(
            recommendations_df,
            x=score_col,
            nbins=50,
            title='Distribution of Similarity Scores',
            labels={score_col: 'Similarity Score', 'count': 'Number of Lecturers'}
        )
    except Exception as e:
        print(f"Error creating histogram: {e}")
        fig2 = None

    # Department-wise analysis if department column exists
    fig3 = None
    dept_candidates = ['Department', 'Dept', 'Faculty', 'School']
    dept_col = None
    
    for candidate in dept_candidates:
        if candidate in recommendations_df.columns:
            dept_col = candidate
            break
    
    if dept_col:
        try:
            dept_stats = recommendations_df.groupby(dept_col).agg({
                score_col: ['mean', 'count']
            }).round(3)
            dept_stats.columns = ['Average_Score', 'Count']
            dept_stats = dept_stats.reset_index().sort_values('Average_Score', ascending=False)

            fig3 = px.scatter(
                dept_stats,
                x='Count',
                y='Average_Score',
                size='Count',
                hover_data=[dept_col],
                title='Department-wise Expertise Analysis',
                labels={'Count': 'Number of Lecturers', 'Average_Score': 'Average Similarity Score'}
            )
        except Exception as e:
            print(f"Error creating department analysis: {e}")
            fig3 = None

    return fig1, fig2, fig3

def main():
    st.markdown('<h1 class="main-header">📚 Thesis Abstract Recommendation System</h1>', unsafe_allow_html=True)

    st.markdown("""
    This system analyzes thesis abstracts and recommends the most suitable internal examiners
    based on similarity with published research works of university lecturers.
    """)

    # Sidebar for input
    st.sidebar.header("Enter Thesis Abstract")

    target_abstract = st.sidebar.text_area(
        "Paste the thesis abstract here:",
        height=300,
        placeholder="Enter or paste the complete thesis abstract that you want to find suitable internal examiners for...",
        help="Enter the full abstract text. The system will analyze this text to find the most suitable internal examiners based on similarity with published research."
    )

    # Main content area
    if target_abstract and target_abstract.strip():
        st.subheader("📋 Target Abstract")
        with st.expander("View Abstract", expanded=False):
            st.write(target_abstract)

        # Add word count and basic validation
        word_count = len(target_abstract.split())
        st.info(f"Abstract contains {word_count} words")

        if word_count < 50:
            st.warning("⚠️ Abstract seems quite short. For better recommendations, consider providing a more detailed abstract.")

        # Load data
        if st.button("🔍 Find Recommendations", type="primary"):
            with st.spinner("Loading datasets..."):
                scopus_data, futa_authors = load_data()

            if scopus_data is not None and futa_authors is not None:
                st.success(f"Loaded {len(scopus_data)} papers and {len(futa_authors)} FUTA authors")

                # Calculate similarities
                with st.spinner("Calculating similarities..."):
                    similarity_results = calculate_similarity(target_abstract, scopus_data)

                # Process results
                with st.spinner("Processing recommendations..."):
                    recommendations = process_author_ids(similarity_results, futa_authors)

                st.session_state.recommendations = recommendations
                st.session_state.processed_data = similarity_results

                st.success("✅ Recommendations generated successfully!")

    elif not target_abstract:
        st.info("👈 Please enter a thesis abstract in the sidebar to get started.")

    else:
        st.warning("Please enter a valid thesis abstract.")

    # Display results
    if st.session_state.recommendations is not None:
        recommendations = st.session_state.recommendations

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Matches", len(recommendations))

        with col2:
            st.metric("Avg Similarity", f"{recommendations['Score'].mean():.3f}")

        with col3:
            st.metric("Max Similarity", f"{recommendations['Score'].max():.3f}")

        with col4:
            st.metric("Top 20 Avg", f"{recommendations.head(20)['Score'].mean():.3f}")

        # Tabs for different views
        tab1, tab2, tab3 = st.tabs(["📊 Recommendations", "📈 Analysis", "📋 Raw Data"])

        # Replace the section in your tab1 with this improved version:

        with tab1:
            st.subheader("Top 20 Recommended Internal Examiners")

            # Display top recommendations
            top_20 = recommendations.head(20)
            
            # Debug: Show what columns are actually available
            st.write("Available columns:", list(top_20.columns))
            
            # Create a formatted dataframe for display
            display_df = top_20.copy()
            display_df['Rank'] = range(1, len(display_df) + 1)
            display_df['Similarity Score'] = display_df['Score'].apply(lambda x: f"{x:.3f}")

            # Build display_columns based on what's actually available
            display_columns = ['Rank']
            
            # Check for name column (could be 'Name', 'Author', 'Full Name', etc.)
            name_candidates = ['Name', 'Author', 'Full Name', 'Author Name', 'Authors']
            name_col = None
            for candidate in name_candidates:
                if candidate in display_df.columns:
                    name_col = candidate
                    break
            
            if name_col:
                display_columns.append(name_col)
            else:
                st.error(f"No name column found. Available columns: {list(display_df.columns)}")
                st.stop()
            
            # Check for department column
            if 'Department' in display_df.columns:
                display_columns.append('Department')
            
            # Add similarity score
            display_columns.append('Similarity Score')
            
            # Check for ID column
            id_candidates = ['Auth-ID', 'Author(s) ID', 'ID', 'Author ID']
            id_col = None
            for candidate in id_candidates:
                if candidate in display_df.columns:
                    id_col = candidate
                    break
            
            if id_col:
                display_columns.append(id_col)

            # Filter display_columns to only include columns that actually exist
            final_display_columns = [col for col in display_columns if col in display_df.columns]
            
            st.dataframe(
                display_df[final_display_columns],
                use_container_width=True,
                hide_index=True
            )

            # Download button
            csv = display_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Top 20 Recommendations",
                data=csv,
                file_name="thesis_recommendations.csv",
                mime="text/csv"
            )

        with tab2:
            st.subheader("Similarity Analysis")

            try:
                # Create visualizations
                fig1, fig2, fig3 = create_visualizations(recommendations)

                # Display charts if they were created successfully
                if fig1 is not None:
                    st.plotly_chart(fig1, use_container_width=True)
                else:
                    st.warning("Could not create bar chart visualization")

                if fig2 is not None:
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.warning("Could not create histogram visualization")

                if fig3 is not None:
                    st.plotly_chart(fig3, use_container_width=True)
                else:
                    st.info("Department analysis not available (no department column found)")

            except Exception as e:
                st.error(f"Error creating visualizations: {str(e)}")
                st.write("Available columns in recommendations:", list(recommendations.columns))

            # Statistics
            st.subheader("📊 Statistical Summary")
            col1, col2 = st.columns(2)

            with col1:
                st.write("**Score Distribution:**")
                if 'Score' in recommendations.columns:
                    st.write(recommendations['Score'].describe())
                else:
                    # Find the first numeric column
                    numeric_cols = recommendations.select_dtypes(include=[np.number]).columns
                    if len(numeric_cols) > 0:
                        score_col = numeric_cols[0]
                        st.write(f"**{score_col} Distribution:**")
                        st.write(recommendations[score_col].describe())
                    else:
                        st.write("No numeric columns found for statistics")

            with col2:
                # Find department column
                dept_candidates = ['Department', 'Dept', 'Faculty', 'School']
                dept_col = None
                for candidate in dept_candidates:
                    if candidate in recommendations.columns:
                        dept_col = candidate
                        break
                
                if dept_col:
                    st.write(f"**Top {dept_col}s:**")
                    score_col = 'Score' if 'Score' in recommendations.columns else recommendations.select_dtypes(include=[np.number]).columns[0]
                    dept_analysis = recommendations.groupby(dept_col)[score_col].agg(['mean', 'count']).sort_values('mean', ascending=False)
                    st.write(dept_analysis.head(10))
                else:
                    st.write("**Data Overview:**")
                    st.write(f"Total recommendations: {len(recommendations)}")
                    st.write(f"Available columns: {len(recommendations.columns)}")
                    st.write(f"Columns: {', '.join(recommendations.columns[:5])}{'...' if len(recommendations.columns) > 5 else ''}")

        with tab3:
            st.subheader("Complete Results")
            st.dataframe(recommendations, use_container_width=True)

            # Download full results
            full_csv = recommendations.to_csv(index=False)
            st.download_button(
                label="📥 Download Complete Results",
                data=full_csv,
                file_name="complete_recommendations.csv",
                mime="text/csv"
            )

    # Information section
    with st.expander("ℹ️ How it works"):
        st.markdown("""
        **The Thesis Abstract Recommendation System works as follows:**

        1. **Input Processing**: Enter your thesis abstract in the text area on the left sidebar.

        2. **Similarity Calculation**:

        3. **Recommendation Generation**: The system matches similarity scores with FUTA authors and ranks them by relevance.

        4. **Visualization**: Results are presented through interactive charts and detailed tables.

        **Key Features:**
        - Simple text input interface
        - Multiple similarity metrics
        - Interactive visualizations
        - Downloadable results
        - Department-wise analysis

        **Tips for better results:**
        - Provide a detailed abstract (at least 50 words)
        - Include key technical terms and methodologies
        - Mention the research domain clearly
        """)

    # Footer
    st.markdown("---")
    st.markdown("**Thesis Abstract Recommendation System** - Developed for FUTA Internal Examiner Selection")

if __name__ == "__main__":
    main()

