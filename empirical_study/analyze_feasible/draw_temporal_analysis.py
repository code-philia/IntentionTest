"""
Visualization script for temporal candidate analysis.

This script generates 3D polygon plots for:
1. Reference Availability (RA) - What fraction of tests have at least one reference?
2. Reference Level (RL) - On average, how many references does each test have?

Generates visualizations for:
- All projects
- Selected 5 projects (spark, yavi, lambda, truth, itext-java)

X-axis: TC Threshold from 0.1 to 0.9 (step 0.1)
Y-axis: Project names
Z-axis: Metric values
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection

# Configuration
stat_dir = 'data/temporal_candidate_analysis'

# All projects
all_projects = ['awesome-algorithm', 'blade', 'cron-utils', 'hutool', 'imglib', 
                'itext-java', 'jInstagram', 'lambda', 'ofdrw', 'RocketMQC', 'spark', 'truth', 'yavi']

# Selected 5 projects for focused visualization
# selected_projects = ['spark', 'yavi', 'lambda', 'truth', 'itext-java']
selected_projects = ['spark', 'ofdrw', 'cron-utils', 'itext-java', 'truth']

# TC thresholds: 0.1 to 0.9 with step 0.1 (9 values total)
tc_thres_values = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def load_metric_1d(project_name, metric_name):
    """Load 1D metric (ra or rl) - array is already 0.1-0.9."""
    file_path = f'{stat_dir}/{project_name}_{metric_name}.npy'
    try:
        data_1d = np.load(file_path)  # Shape: [9] for thresholds 0.1-0.9
        return data_1d
    except FileNotFoundError:
        print(f'Warning: {file_path} not found, skipping {project_name}')
        return None


def polygon_under_graph(xlist, ylist):
    """
    Construct the vertex list which defines the polygon filling the space under
    the (xlist, ylist) line graph. Assumes the xs are in ascending order.
    """
    return [(xlist[0], 0.), *zip(xlist, ylist), (xlist[-1], 0.)]


def draw(project_names, z_axis_data, title, output_file, z_label='RA', z_max=1.0, decimal_places=2):
    """
    Draw 3D polygon visualization following the style of draw_feasible_for_all_project_specify_tc_thres.py
    """
    fig = plt.figure(dpi=200)
    ax = fig.add_subplot(111, projection='3d')

    # Make verts a list, verts[i] will be a list of (x,y) pairs defining polygon i
    verts = []

    # Set up the x sequence (TC thresholds)
    xs = np.array(tc_thres_values)

    # The ith polygon will appear on the plane y = zs[i]
    zs = range(len(z_axis_data))

    for i in zs:
        ys = z_axis_data[i]
        verts.append(polygon_under_graph(xs, ys))

    poly = PolyCollection(verts, 
                        facecolors=[plt.cm.viridis(i/len(z_axis_data)) for i in range(len(z_axis_data))], 
                        alpha=.3)
    poly.set_edgecolor('k')  # Add edge color for better distinction between polygons

    ax.add_collection3d(poly, zs=zs, zdir='y')

    ax.set_xlabel('Threshold', fontsize=8)
    ax.set_ylabel('Project', fontsize=8)
    ax.set_zlabel(z_label, fontsize=8)

    ax.set_xlim(0.1, 0.9)
    ax.set_xticks([0.1, 0.3, 0.5, 0.7, 0.9])
    ax.tick_params(axis='x', which='major', labelsize=7)

    ax.set_yticks(range(len(project_names)))
    ax.set_yticklabels(project_names, fontsize=7)

    ax.set_zlim(0, z_max)
    ax.tick_params(axis='z', which='major', labelsize=7)

    ax.grid(False)

    # Annotate values at every other threshold (0.1, 0.3, 0.5, 0.7, 0.9)
    for i in range(len(project_names)):
        for j in range(0, len(tc_thres_values), 2):  # Every other threshold
            x = tc_thres_values[j]
            y = i
            z = z_axis_data[i][j]
            ax.text(x, y, z, f'{z:.{decimal_places}f}', fontsize=8, color='black')
            ax.scatter(x, y, z, color='black', s=3)

    # Connect points with the same x-axis value using dotted lines
    for j in range(0, len(tc_thres_values), 2):
        x = tc_thres_values[j]
        z_values = [z_axis_data[i][j] for i in range(len(project_names))]
        ax.plot([x] * len(project_names), range(len(project_names)), z_values, 
                color='gray', linestyle='--', linewidth=0.7)

    plt.title(title, fontsize=10)
    plt.savefig(output_file, dpi=200, bbox_inches='tight')
    print(f'Saved: {output_file}')
    plt.close()


def load_projects_data(project_names, metric_name):
    """Load metric data for a list of projects."""
    data_list = []
    valid_projects = []
    
    for project_name in project_names:
        data = load_metric_1d(project_name, metric_name)
        if data is not None:
            data_list.append(data)
            valid_projects.append(project_name)
    
    return valid_projects, data_list


def main():
    print(f'Creating temporal analysis visualizations...')
    print(f'TC thresholds: {tc_thres_values}\n')
    
    # Load data for all projects
    print('Processing all projects...')
    all_valid_projects, all_ra_data = load_projects_data(all_projects, 'ra')
    _, all_rl_data = load_projects_data(all_projects, 'rl')
    
    if len(all_valid_projects) > 0:
        # Determine max RL for z-axis scaling
        max_rl = max(max(rl) for rl in all_rl_data) * 1.1  # Add 10% margin
        
        # Draw RA for all projects (0-1 scale, 2 decimal places)
        draw(all_valid_projects, all_ra_data, 
             'Reference Availability (RA) - All Projects',
             f'{stat_dir}/temporal_analysis_ra_all_projects.pdf',
             z_label='RA', z_max=1.03, decimal_places=2)
        
        # Draw RL for all projects (1 decimal place)
        draw(all_valid_projects, all_rl_data,
             'Reference Level (RL) - All Projects',
             f'{stat_dir}/temporal_analysis_rl_all_projects.pdf',
             z_label='RL (avg)', z_max=max_rl, decimal_places=1)
    
    # Load data for selected projects
    print('\nProcessing selected projects...')
    sel_valid_projects, sel_ra_data = load_projects_data(selected_projects, 'ra')
    _, sel_rl_data = load_projects_data(selected_projects, 'rl')
    
    if len(sel_valid_projects) > 0:
        # Determine max RL for z-axis scaling
        max_rl = max(max(rl) for rl in sel_rl_data) * 1.1  # Add 10% margin
        
        # Draw RA for selected projects (0-1 scale, 2 decimal places)
        draw(sel_valid_projects, sel_ra_data,
             'Reference Availability (RA) - Selected Projects',
             f'{stat_dir}/temporal_analysis_ra_selected_projects.pdf',
             z_label='RA', z_max=1.03, decimal_places=2)
        
        # Draw RL for selected projects (1 decimal place)
        draw(sel_valid_projects, sel_rl_data,
             'Reference Level (RL) - Selected Projects',
             f'{stat_dir}/temporal_analysis_rl_selected_projects.pdf',
             z_label='RL (avg)', z_max=max_rl, decimal_places=1)
    
    print('\nAll visualizations completed!')
    print(f'Generated 4 figures: RA and RL for both all projects and selected projects')


if __name__ == '__main__':
    main()