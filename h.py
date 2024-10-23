import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
from graphviz import Digraph
import json
import os
import threading
import socket
import http.server
import socketserver
import plotly.express as px
from io import BytesIO
import base64
import tempfile

st.set_page_config(layout = 'wide', page_title="Hakim")
hide_st_style = """
    <style>
    /* Hide the main menu */
    #MainMenu {visibility: hidden;}
    
    /* Hide the footer */
    footer {visibility: hidden;}
    
    /* Hide the header */
    header {visibility: hidden;}
    
    /* Optionally hide the hamburger menu (if present) */
    .css-1kyxreq.edgvbvh3 {visibility: hidden;}
    </style>
    """

st.markdown(hide_st_style, unsafe_allow_html=True)

@st.cache_data
def load_excel(file_path):
    try:
        return pd.read_excel(file_path)
    except Exception as e:
        st.error(f"Error loading Excel file: {e}")
        return pd.DataFrame()

@st.cache_data
def load_csv(file_path):
    try:
        return pd.read_csv(file_path)
    except Exception as e:
        st.error(f"Error loading CSV file: {e}")
        return pd.DataFrame()

# Function to format website links
def format_website(url):
    if pd.isna(url):
        return ''
    if not url.startswith(('http://', 'https://')):
        return 'http://' + url
    return url

# Function to shorten practice names
def shorten_practice_name(name):
    parts = name.split()
    if len(parts) == 2:
        return f"{parts[0]} {parts[1]}"
    elif '-' in name:
        hyphen_index = parts.index('-')
        return f"{parts[0]} {parts[hyphen_index + 1]}"
    return parts[0]

# Paths to your files
excel_file_path = 'Coy Details.xlsx'
json_file_path = 'organization_structures.json'
practice_coords_file_path = 'Practice Coords.csv'

# Load the Excel and CSV files
df = load_excel(excel_file_path)
coords_df = load_csv(practice_coords_file_path)

# Ensure that the necessary columns exist before merging
required_columns = ['Practice Name', 'Post Code', 'Full Address', 'Latitude', 'Longitude']
for col in required_columns:
    if col not in coords_df.columns:
        st.error(f"Missing column in Practice Coords CSV: {col}")

# Ensure all rows are included by checking for missing data
df.dropna(how='all', inplace=True)

# Format the website links
df['Website'] = df['Website'].apply(format_website)

# Concatenate 'Address' and 'Post Code' to form the complete address
df['Full Address'] = df['Address'] + ', ' + df['Post Code']

# Correctly parse the acquisition date and handle errors
df['Acquisition date'] = pd.to_datetime(df['Acquisition date'], errors='coerce')

# Replace missing acquisition dates with '1900-01-01'
df['Acquisition date'] = df['Acquisition date'].fillna(pd.Timestamp('1900-01-01'))

# Merge coordinates with the main dataframe
try:
    df = df.merge(coords_df, on=['Practice Name', 'Post Code', 'Full Address'], how='left')
except Exception as e:
    st.error(f"Error merging data: {e}")

# Handle any remaining missing coordinates with fallback coordinates
fallback_coordinates = (53.3498, -6.2603)  # Coordinates for Dublin as fallback
df['Latitude'] = df['Latitude'].fillna(fallback_coordinates[0])
df['Longitude'] = df['Longitude'].fillna(fallback_coordinates[1])

# Shorten practice names for visualization
df['Short Practice Name'] = df['Practice Name'].apply(shorten_practice_name)

# Load existing organizational structures from a JSON file
if os.path.exists(json_file_path):
    with open(json_file_path, 'r') as f:
        organizations = json.load(f)
else:
    organizations = {}

# Function to create the Graphviz chart
def create_org_chart(organization):
    dot = Digraph()
    for role, info in organization.items():
        dot.node(role, f"{role}\n{info['name']}")
        for report in info.get("reports", []):
            dot.edge(role, report)
    return dot

def display_structure(role, organization):
    if role in organization:
        st.subheader(f"{role}: {organization[role]['name']}")
        reports = organization[role].get("reports", [])
        if reports:
            st.write("Reports to:")
            for report in reports:
                if st.button(report):
                    display_structure(report, organization)

def save_organizations():
    with open(json_file_path, 'w') as f:
        json.dump(organizations, f, indent=4)

def admin_page():
    st.header("Admin Page")
    practice_names = list(df['Practice Name'].unique())
    selected_practice = st.selectbox("Select Practice Name to Manage", practice_names)

    if selected_practice:
        st.write(f"Managing organizational structure for: **{selected_practice}**")

        organization = organizations.get(selected_practice, {})

        # Add a new role
        with st.form(key="add_role_form"):
            st.subheader("Add a new role")
            new_role = st.text_input("Role")
            new_name = st.text_input("Name")
            new_reports = st.text_input("Reports (comma-separated)")
            if st.form_submit_button("Add Role"):
                if new_role and new_name:
                    reports_list = [report.strip() for report in new_reports.split(",")]
                    organization[new_role] = {"name": new_name, "reports": reports_list}
                    organizations[selected_practice] = organization
                    save_organizations()
                    st.success(f"Added {new_role} to {selected_practice}")

        # Edit an existing role
        if organization:
            with st.form(key="edit_role_form"):
                st.subheader("Edit an existing role")
                edit_role = st.selectbox("Select a role to edit", list(organization.keys()))
                new_name = st.text_input("New Name", value=organization[edit_role]["name"])
                new_reports = st.text_input("New Reports (comma-separated)", value=", ".join(organization[edit_role]["reports"]))
                if st.form_submit_button("Edit Role"):
                    if edit_role and new_name:
                        reports_list = [report.strip() for report in new_reports.split(",")]
                        organization[edit_role] = {"name": new_name, "reports": reports_list}
                        organizations[selected_practice] = organization
                        save_organizations()
                        st.success(f"Updated {edit_role} in {selected_practice}")

        # Delete a role
        if organization:
            with st.form(key="delete_role_form"):
                st.subheader("Delete a role")
                delete_role = st.selectbox("Select a role to delete", list(organization.keys()))
                if st.form_submit_button("Delete Role"):
                    if delete_role in organization:
                        del organization[delete_role]
                        organizations[selected_practice] = organization
                        save_organizations()
                        st.success(f"Deleted {delete_role} from {selected_practice}")

def main():
    st.title("Practice Details and Organizational Structure")

    st.sidebar.header("User Actions")

    # User types the first letter(s)
    search_input = st.sidebar.text_input("Type the first 1-3 letters of Practice Name").upper()

    if search_input:
        practice_names = sorted([name for name in df['Practice Name'].unique() if name.upper().startswith(search_input)])
        practice_name = st.sidebar.selectbox("Select Practice Name", practice_names)

        if practice_name:
            st.sidebar.markdown("### Practice Details")

            # Initialize session state for map style and role selection
            if 'map_style' not in st.session_state:
                st.session_state.map_style = 'OpenStreetMap'
            if 'selected_role' not in st.session_state:
                st.session_state.selected_role = 'None'

            # Select Map Style
            map_style = st.sidebar.selectbox(
                "Select Map Style",
                ["OpenStreetMap", "Google Satellite"],
                index=["OpenStreetMap", "Google Satellite"].index(st.session_state.map_style)
            )

            # Update session state when the dropdown changes
            if map_style != st.session_state.map_style:
                st.session_state.map_style = map_style
                st.experimental_rerun()

            # Filter the dataframe based on the selected Practice Name
            selected_practice = df[df['Practice Name'] == practice_name].iloc[0]

            # Map style to tiles and attribution mapping
            tiles = {
                "OpenStreetMap": "OpenStreetMap",
                "Google Satellite": "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
            }

            attribution = {
                "OpenStreetMap": None,
                "Google Satellite": "Google"
            }

            # Function to create the map
            def create_map(style):
                map_center = [selected_practice['Latitude'], selected_practice['Longitude']]
                m = folium.Map(location=map_center, zoom_start=15, tiles=tiles[style], attr=attribution[style])
                popup_text = f"{selected_practice['Practice Name']}<br>{selected_practice['Full Address']}"
                folium.Marker(
                    location=[selected_practice['Latitude'], selected_practice['Longitude']],
                    popup=popup_text,
                    icon=folium.Icon(color='blue', icon='info-sign')
                ).add_to(m)
                return m

            # Display Address
            st.write(f"**Address:** {selected_practice['Full Address']}")

            # Create and display the map based on the selected style
            m = create_map(st.session_state.map_style)
            folium_static(m, width=300, height=200)

            # Save the map to a temporary HTML file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
                m.save(tmp_file.name)
                map_path = tmp_file.name

            # Encode the HTML file in base64
            with open(map_path, 'rb') as f:
                map_base64 = base64.b64encode(f.read()).decode()

            # Provide a link to open the full-size map in a new tab
            html_link = f'<a href="data:text/html;base64,{map_base64}" target="_blank">Open Full-Size Map</a>'
            st.markdown(html_link, unsafe_allow_html=True)

            # Adjust the CSS to make the dropdown the same width as the map
            st.markdown(
                """
                <style>
                .stSelectbox {
                    max-width: 300px;
                }
                .stGraphvizChart > div {
                    margin: auto;
                }
                </style>
                """,
                unsafe_allow_html=True
            )

            # Display Practice Details and Top Management Details in columns
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### Practice Information")
                acquisition_date = "None Provided" if selected_practice['Acquisition date'] == pd.Timestamp('1900-01-01') else selected_practice['Acquisition date'].strftime('%Y-%m-%d')
                st.markdown(f"""
                **Practice Name:** {selected_practice['Practice Name']}  
                **Legal Entity:** {selected_practice['Legal Entity']}  
                **Company No:** {selected_practice['Company No']}  
                **VAT Number:** {selected_practice['VAT Number']}  
                **Acquisition date:** {acquisition_date}  
                **Country:** {selected_practice['Country']}  
                **Telephone No:** {selected_practice['Telephone No']}  
                **Website:** {'[Link](' + selected_practice['Website'] + ')' if selected_practice['Website'] else 'N/A'}  
                **Practice email:** {selected_practice['Practice email']}  
                **Group Shares (%):** {selected_practice['Hakim Group Shares (%)']}
                """)

            with col2:
                st.markdown("### Top Management Details")
                details = []

                for i in range(1, 7):
                    if not pd.isna(selected_practice[f'Shark {i} (name)']):
                        details.append(f"**Shark {i} Name:** {selected_practice[f'Shark {i} (name)']}")
                    if not pd.isna(selected_practice[f'Shark {i} (email address)']):
                        details.append(f"**Shark {i} Email Address:** {selected_practice[f'Shark {i} (email address)']}")
                    if not pd.isna(selected_practice[f'Shark {i} (shareholding - %)']):
                        details.append(f"**Shark {i} Shareholding - %:** {selected_practice[f'Shark {i} (shareholding - %)']}  \n")

                for i in range(1, 6):
                    if not pd.isna(selected_practice[f'Fish {i} (name)']):
                        details.append(f"**Fish {i} Name:** {selected_practice[f'Fish {i} (name)']}")
                    if not pd.isna(selected_practice[f'Fish {i} (email)']):
                        details.append(f"**Fish {i} Email:** {selected_practice[f'Fish {i} (email)']}")

                if not pd.isna(selected_practice['Primary Buddy']):
                    details.append(f"**Primary Buddy:** {selected_practice['Primary Buddy']}")
                if not pd.isna(selected_practice['Secondary Buddy']):
                    details.append(f"**Secondary Buddy:** {selected_practice['Secondary Buddy']}")
                if not pd.isna(selected_practice['Senior Buddy']):
                    details.append(f"**Senior Buddy:** {selected_practice['Senior Buddy']}")
                if not pd.isna(selected_practice['ID']):
                    details.append(f"**ID:** {selected_practice['ID']}")

                st.markdown('  \n'.join(details))

            # Practice Structure button
            if st.button("Practice Structure"):
                st.header(f"Organizational Structure for {practice_name}")
                if practice_name in organizations:
                    organization = organizations[practice_name]
                    org_chart = create_org_chart(organization)
                    st.graphviz_chart(org_chart)
                    
                    # Select role dropdown
                    roles = list(organization.keys())
                    roles.insert(0, 'None')
                    selected_role = st.selectbox(
                        "Select a role to start with", 
                        roles,
                        index=roles.index(st.session_state.selected_role)
                    )
                    if selected_role != st.session_state.selected_role:
                        st.session_state.selected_role = selected_role
                        st.experimental_rerun()
                    if st.session_state.selected_role != 'None':
                        display_structure(st.session_state.selected_role, organization)
                else:
                    st.write("No organizational structure data available for this practice.")

    st.sidebar.title("Toggle By Acquisitions")
    show_acquisitions = st.sidebar.checkbox("Toggle Acquisitions")

    df_valid_dates = df[df['Acquisition date'] != pd.Timestamp('1900-01-01')]
    df_no_acquisition = df[df['Acquisition date'] == pd.Timestamp('1900-01-01')]

    if show_acquisitions:
        st.sidebar.markdown("#### Acquisitions: All Years")
        general_acquisition = st.sidebar.checkbox("Show All Acquisitions")

        if general_acquisition:
            # Plotly visualization: Number of acquisitions by year (general)
            acquisitions_by_year = df_valid_dates['Acquisition date'].dt.year.value_counts().sort_index()
            acquisitions_by_year = acquisitions_by_year[acquisitions_by_year > 0]  # Exclude years with zero acquisitions
            fig = px.bar(acquisitions_by_year, x=acquisitions_by_year.index, y=acquisitions_by_year.values,
                         labels={'x': 'Year', 'y': 'Number of Acquisitions'}, title='Number of Acquisitions by Year',
                         height=500, text=acquisitions_by_year.values)  # Add numbers on bars
            fig.update_traces(marker_color='blue')  # Remove colors
            st.plotly_chart(fig)

        st.sidebar.markdown("#### Yearly Acquisitions")
        years = sorted(df_valid_dates['Acquisition date'].dt.year.unique())
        selected_years = []
        for year in years:
            if st.sidebar.checkbox(f"Show {year}"):
                selected_years.append(year)

        col1, col2 = st.columns(2)  # Layout in 2 columns

        for i, year in enumerate(selected_years):
            if i % 2 == 0:
                with col1:
                    st.markdown(f"### Acquisitions in {year}")
                    acquisitions_in_year = df_valid_dates[df_valid_dates['Acquisition date'].dt.year == year]
                    acquisitions_in_year['Month'] = acquisitions_in_year['Acquisition date'].dt.strftime('%B')
                    acquisitions_in_year['Month'] = pd.Categorical(acquisitions_in_year['Month'], categories=[
                        'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'], ordered=True)
                    acquisitions_by_month = acquisitions_in_year.groupby(['Month']).size().reset_index(name='Count')
                    fig = px.bar(acquisitions_by_month, x='Month', y='Count',
                                 labels={'Count': 'Number of Acquisitions'}, title=f'Number of Acquisitions in {year} by Month',
                                 width=450, height=400, text='Count')  # Add numbers on bars
                    fig.update_layout(yaxis=dict(tickformat='d'))  # Remove decimal numbers from y-axis
                    fig.update_traces(marker_color='blue', width=0.5)  # Remove colors and make bars narrower
                    st.plotly_chart(fig)
                    if st.button(f"View {year}"):
                        view_data = acquisitions_in_year[['Practice Name', 'Acquisition date', 'Country']].reset_index(drop=True)
                        view_data['Acquisition date'] = view_data['Acquisition date'].dt.strftime('%Y-%m-%d')
                        st.write(view_data)
            else:
                with col2:
                    st.markdown(f"### Acquisitions in {year}")
                    acquisitions_in_year = df_valid_dates[df_valid_dates['Acquisition date'].dt.year == year]
                    acquisitions_in_year['Month'] = acquisitions_in_year['Acquisition date'].dt.strftime('%B')
                    acquisitions_in_year['Month'] = pd.Categorical(acquisitions_in_year['Month'], categories=[
                        'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'], ordered=True)
                    acquisitions_by_month = acquisitions_in_year.groupby(['Month']).size().reset_index(name='Count')
                    fig = px.bar(acquisitions_by_month, x='Month', y='Count',
                                 labels={'Count': 'Number of Acquisitions'}, title=f'Number of Acquisitions in {year} by Month',
                                 width=450, height=400, text='Count')  # Add numbers on bars
                    fig.update_layout(yaxis=dict(tickformat='d'))  # Remove decimal numbers from y-axis
                    fig.update_traces(marker_color='blue', width=0.5)  # Remove colors and make bars narrower
                    st.plotly_chart(fig)
                    if st.button(f"View {year}"):
                        view_data = acquisitions_in_year[['Practice Name', 'Acquisition date', 'Country']].reset_index(drop=True)
                        view_data['Acquisition date'] = view_data['Acquisition date'].dt.strftime('%Y-%m-%d')
                        st.write(view_data)

        st.sidebar.markdown("#### Practices with No Acquisition Date")
        show_no_acquisition = st.sidebar.checkbox("No Acquisition Date")
        
        if show_no_acquisition:
            st.markdown("### Practices with No Acquisition Date")
            view_data = df_no_acquisition[['Practice Name', 'Acquisition date', 'Country']].reset_index(drop=True)
            view_data['Acquisition date'] = view_data['Acquisition date'].dt.strftime('%Y-%m-%d')
            st.write(view_data)

    st.sidebar.title("Admin")
    admin_section = st.sidebar.expander("Admin Login", expanded=False)
    with admin_section:
        password = st.text_input("Enter admin password", type="password")
        if password == "admin":  # Replace with your actual password
            admin_page()
        else:
            st.error("Incorrect password")

    st.sidebar.header("Search Filter & Download")
    show_filters = st.sidebar.checkbox("Show Filters")

    if show_filters:
        # Filter Types
        st.sidebar.header("Filter Types")
        filter_type = st.sidebar.radio("Select Filter Type", ["Defined Criteria Filter", "Random Filter", "Upload and Filter"])

        if filter_type == "Defined Criteria Filter":
            st.sidebar.header("Defined Criteria Filter")

            # Allow multiple search criteria
            num_criteria = st.sidebar.number_input("Number of Search Criteria", min_value=1, max_value=5, value=1)
            search_terms = []
            for i in range(num_criteria):
                search_terms.append(st.sidebar.text_input(f"Search Criterion {i+1}"))

            if any(search_terms):
                def multiple_search(row):
                    return all(term.lower() in str(row).lower() for term in search_terms if term)
                filtered_df = df[df.apply(multiple_search, axis=1)]

                st.sidebar.header("Select Columns")
                columns = filtered_df.columns.tolist()
                selected_columns = []
                for column in columns:
                    if st.sidebar.checkbox(column):
                        selected_columns.append(column)

                filtered_df = filtered_df[selected_columns]

                # Remove trailing zeros in date columns
                for col in filtered_df.select_dtypes(include=['datetime64[ns]']).columns:
                    filtered_df[col] = filtered_df[col].dt.strftime('%Y-%m-%d')

                st.write("### Search Results")
                st.dataframe(filtered_df)

                csv = filtered_df.to_csv(index=False)
                b64 = base64.b64encode(csv.encode()).decode()  # B64 encode
                href = f'<a href="data:file/csv;base64,{b64}" download="filtered_practices.csv">Download CSV file</a>'
                st.markdown(href, unsafe_allow_html=True)

        elif filter_type == "Random Filter":
            st.sidebar.header("Random Filter")
            practice_list_input = st.sidebar.text_area("Enter a list of practice names (one per line):")
            
            if practice_list_input:
                practice_list = practice_list_input.splitlines()
                filtered_df = df[df['Practice Name'].isin(practice_list)]

                st.sidebar.header("Select Columns")
                columns = filtered_df.columns.tolist()
                selected_columns = []
                for column in columns:
                    if st.sidebar.checkbox(column):
                        selected_columns.append(column)

                filtered_df = filtered_df[selected_columns]

                # Remove trailing zeros in date columns
                for col in filtered_df.select_dtypes(include=['datetime64[ns]']).columns:
                    filtered_df[col] = filtered_df[col].dt.strftime('%Y-%m-%d')
                
                st.write("### Report for Selected Practices")
                st.dataframe(filtered_df)
                
                csv = filtered_df.to_csv(index=False)
                b64 = base64.b64encode(csv.encode()).decode()  # B64 encode
                href = f'<a href="data:file/csv;base64,{b64}" download="selected_practices.csv">Download CSV file</a>'
                st.markdown(href, unsafe_allow_html=True)

        elif filter_type == "Upload and Filter":
            st.sidebar.header("Upload and Filter")
            uploaded_file = st.sidebar.file_uploader("Upload an Excel or CSV file with practice names", type=["csv", "xlsx"])
            
            if uploaded_file:
                if uploaded_file.name.endswith(".csv"):
                    uploaded_df = pd.read_csv(uploaded_file)
                else:
                    uploaded_df = pd.read_excel(uploaded_file)
                practice_list = uploaded_df.iloc[:, 0].tolist()
                filtered_df = df[df['Practice Name'].isin(practice_list)]

                st.sidebar.header("Select Columns")
                columns = filtered_df.columns.tolist()
                selected_columns = []
                for column in columns:
                    if st.sidebar.checkbox(column):
                        selected_columns.append(column)

                filtered_df = filtered_df[selected_columns]

                # Remove trailing zeros in date columns
                for col in filtered_df.select_dtypes(include=['datetime64[ns]']).columns:
                    filtered_df[col] = filtered_df[col].dt.strftime('%Y-%m-%d')
                
                st.write("### Report for Uploaded Practices")
                st.dataframe(filtered_df)
                
                csv = filtered_df.to_csv(index=False)
                b64 = base64.b64encode(csv.encode()).decode()  # B64 encode
                href = f'<a href="data:file/csv;base64,{b64}" download="uploaded_practices.csv">Download CSV file</a>'
                st.markdown(href, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
