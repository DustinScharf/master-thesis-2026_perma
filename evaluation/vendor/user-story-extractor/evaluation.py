import argparse
import copy
import csv
import json
import matplotlib.pyplot as plt
import numpy as np
import os
import seaborn as sns
import stanza
import subprocess
import sys
import re
import statistics
import logging
from bert_score import score

logging.getLogger("transformers").setLevel(logging.ERROR)

def compare_and_get_results(baseline_data, experiment_data, comparison_mode, pos_data, stanza_pos_nlp):
    '''
    Runs all the functions that will compare and get the results of the comparison for each backlog.

    Parameters:
    baseline_data (2D list): contains text, persona, primary entities, and primary actions identified by the baseline data
    experiment_data (2D list): contains text, persona, primary entities, and primary actions identified by the experiment
    comparison_mode (int): determines the mode of comparing (1-strict, 2-inclusive, 3-relaxed)
    pos_data (3D list): contains the pos data of persona, entity, and action
    stanza_pos_nlp (class): runs the stanza application to get the tags

    Returns:
    story_results (3D list): has the precision, recall and f-measure of each story for the persona, action, entity
    count_list (3D list): has the count for persona, entity, action results for each story for the number of true/false postive and false negative
    comparison_collection (3D list): has the elements for persona, entity, action results for each story for the elements that are true/false postive and false negative
    missing_stories (2D list): missing stories from baseline_data and experiment 
    baseline_text (list): story text in order based on evaluation order
    '''
    sorted_baseline_data, sorted_experiment_data, sorted_pos, missing_stories = sort(baseline_data, experiment_data, pos_data)
    baseline_text, baseline_persona, baseline_entity, baseline_action, baseline_benefit = sorted_baseline_data
    _, experiment_persona, experiment_entity, experiment_action, experiment_benefit = sorted_experiment_data

    persona_comparison_collection = []
    entity_comparison_collection = []
    action_comparison_collection = []
    benefit_comparison_collection = []

    count_persona_comparison_list = []
    count_entity_comparison_list = []
    count_action_comparison_list = []
    count_benefit_comparison_list = []
   
    for i in range(len(baseline_text)):
        #Strict comparison 
        if comparison_mode == 1:
            persona_comparison = strict_compare(baseline_persona[i], experiment_persona[i])
            entity_comparison = strict_compare(baseline_entity[i], experiment_entity[i])
            action_comparison = strict_compare(baseline_action[i], experiment_action[i])
            benefit_comparison = strict_compare(baseline_benefit[i], experiment_benefit[i])
            
        #Inclusion comparison
        elif comparison_mode == 2:
            persona_comparison = inclusion_compare(baseline_persona[i], experiment_persona[i])
            entity_comparison = inclusion_compare(baseline_entity[i], experiment_entity[i])
            action_comparison = inclusion_compare(baseline_action[i], experiment_action[i])
            benefit_comparison = inclusion_compare(baseline_benefit[i], experiment_benefit[i])
        #relaxed comparison
        else:
            persona_pos, entity_pos, action_pos = sorted_pos
            persona_comparison = relaxed_compare(baseline_persona[i], experiment_persona[i], persona_pos[i], stanza_pos_nlp)
            entity_comparison = relaxed_compare(baseline_entity[i], experiment_entity[i], entity_pos[i], stanza_pos_nlp)
            action_comparison = relaxed_compare(baseline_action[i], experiment_action[i], action_pos[i], stanza_pos_nlp)
            # relaxed comparison is not possible because the benefit is not annotated in the pos data
            benefit_comparison = None

        persona_comparison_collection.append(persona_comparison)
        entity_comparison_collection.append(entity_comparison)
        action_comparison_collection.append(action_comparison)

        count_persona_comparison = count_true_false_positives_negatives(persona_comparison)
        count_entity_comparison = count_true_false_positives_negatives(entity_comparison)
        count_action_comparison = count_true_false_positives_negatives(action_comparison)

        count_persona_comparison_list.append(count_persona_comparison)
        count_entity_comparison_list.append(count_entity_comparison)
        count_action_comparison_list.append(count_action_comparison)
        
        if comparison_mode<3:
            benefit_comparison_collection.append(benefit_comparison)
            count_benefit_comparison = count_true_false_positives_negatives(benefit_comparison)
            count_benefit_comparison_list.append(count_benefit_comparison)

    count_list = [count_persona_comparison_list, count_entity_comparison_list, count_action_comparison_list, count_benefit_comparison_list]
    comparison_collection = [persona_comparison_collection, entity_comparison_collection, action_comparison_collection, benefit_comparison_collection]
    
    story_results = individual_story(count_list)

    return story_results, count_list, comparison_collection, missing_stories, baseline_text

def sort(baseline_data, experiment_data, pos_data):
    '''
    sorts the list in order to match the text, and detect missing stories

    Parameters:
    baseline_data (2D list): contains text, persona, entity, action, and benefit identified by the baseline data
    experiment_data (2D list): contains text, persona, entity, action, and benefit identified by the experiment
    pos_data (3D list): contains the pos data of persona, entity, and action

    Returns:
    sorted_baseline_data(2D list): sorted text, persona, entity, action, and benefit identified of baseline_data (considering missing stories)
    sorted_experiment_data (2D list): sorted text, persona, entity, action, and benefit identified coresponding to baseline_data
    sorted_pos (3d): sorted pos data based on sorted_baseline_data
    missing_stories (2D list): missing stories from baseline_data and experiment
    '''
 
    baseline_text,baseline_persona, baseline_entity, baseline_action, baseline_benefit = baseline_data
    baseline_text = [re.sub(r'#G\d{2}#', '', text) for text in baseline_text]
    persona_pos_data, entity_pos_data, action_pos_data = pos_data
    experiment_data_copy = copy.deepcopy(experiment_data)
    experiment_text, experiment_persona, experiment_entity, experiment_action, experiment_benefit  = experiment_data_copy
    experiment_text = [re.sub(r'#G\d{2}#', '', text) for text in experiment_text]
    
    sorted_baseline_text = []
    sorted_baseline_persona = []
    sorted_baseline_entity = []
    sorted_baseline_action= []
    sorted_baseline_benefit = []

    sorted_experiment_text = []
    sorted_experiment_persona = []
    sorted_experiment_entity = []
    sorted_experiment_action= []
    sorted_experiment_benefit = []

    sorted_persona_pos = []
    sorted_entity_pos = []
    sorted_action_pos = []

    for i in range(len(baseline_text)):
        for j in range(len(experiment_text)):
            if baseline_text[i].strip(" \n\t") == experiment_text[j].strip(" \n\t"):

                sorted_baseline_text.append(baseline_text[i])
                sorted_baseline_persona.append(baseline_persona[i])
                sorted_baseline_entity.append(baseline_entity[i])
                sorted_baseline_action.append(baseline_action[i])
                sorted_baseline_benefit.append(baseline_benefit[i])

                sorted_experiment_text.append(experiment_text[j])
                sorted_experiment_persona.append(experiment_persona[j])
                sorted_experiment_entity.append(experiment_entity[j])
                sorted_experiment_action.append(experiment_action[j])
                sorted_experiment_benefit.append(experiment_benefit[j])

                sorted_persona_pos.append(persona_pos_data[i])
                sorted_entity_pos.append(entity_pos_data[i])
                sorted_action_pos.append(action_pos_data[i])
                
                del experiment_text[j]
                del experiment_persona[j]
                del experiment_entity[j]
                del experiment_action[j]
                del experiment_benefit[j]
                break

    nlp_missing_story = set(baseline_text).difference(set(sorted_baseline_text))
    nlp_missing_story_list = list(nlp_missing_story)

    baseline_missing_story_list = experiment_text

    sorted_baseline_data = [sorted_baseline_text, sorted_baseline_persona, sorted_baseline_entity, sorted_baseline_action, sorted_baseline_benefit]
    sorted_experiment_data = [sorted_experiment_text, sorted_experiment_persona, sorted_experiment_entity, sorted_experiment_action, sorted_experiment_benefit]
    sorted_pos = [sorted_persona_pos, sorted_entity_pos, sorted_action_pos]
    missing_stories = [baseline_missing_story_list, nlp_missing_story_list]

    return sorted_baseline_data, sorted_experiment_data, sorted_pos, missing_stories

def strict_compare (baseline, experiment):
    '''
    calculate the number of true/false positives and false negatives using STRICT comparison

    Parameters:
    baseline (list): the elements being compared to 
    experiment (list): the elements comparing for accuracy 

    Returns:
    comparison_results (2D list): includes the elements identified as true/false positives and false negatives
    '''

    true_positive = []
    false_positive = []

    for i in range(len(experiment)):
        nlp_element = experiment[i].lower().strip()
        not_true_positive = True

        for j in range (len(baseline)):
            baseline_element = baseline[j].lower().strip()

            if nlp_element == baseline_element:
                true_positive.append(baseline[j])
                baseline.pop(j)
                not_true_positive = False
                break

        if not_true_positive:
            false_positive.append(nlp_element)
    
    false_nagative = copy.deepcopy(baseline)

    comparison_results = [true_positive, false_positive, false_nagative]
    

    return comparison_results

def inclusion_compare (baseline, experiment):
    '''
    calculate the number of true/false positives and false negatives for inclusion comparison mode

    Parameters:
    baseline (list): the elements being compared to 
    experiment (list): the elements comparing for accuracy 

    Returns:
    comparison_results (2D list): includes the elements identified as true/false positives and false negatives, including half points
    '''
    true_positive = []
    false_positive = []

    for i in range(len(experiment)):
        nlp_element = experiment[i].lower().strip()
        not_true_positive = True

        #first checks if there are any exact cases
        for j in range (len(baseline)):
            baseline_element = baseline[j].lower().strip()

            if nlp_element == baseline_element:
                true_positive.append(baseline[j])
                baseline.pop(j)
                not_true_positive = False
                break

        #Checks if there is any inlcusions (not including qualifiers)
        if not_true_positive:
            for j in range (len(baseline)):
                baseline_element = baseline[j].lower().strip()
                if check_inclusion_elements(nlp_element, baseline_element):
                    true_positive.append(baseline[j])
                    baseline.pop(j)
                    not_true_positive = False
                    break

        #If it still not identified as true_positive, then the element is a false positive
        if not_true_positive:
            false_positive.append(nlp_element)
    
    false_nagative = copy.deepcopy(baseline)

    comparison_results = [true_positive, false_positive, false_nagative]

    return comparison_results

def check_inclusion_elements(experiment_element, baseline_element):
    '''
    determines if an element is part of another element but does not contain any qualifiers

    Paramters:
    experiment_element (str): element from experiment tool to evaluate if common element exist
    baseline_element (str): element from baseline to evaluate if common element exist

    Returns:
    True if elements considers to be inclusive
    False if elements not consider to be inclusive
    '''
    experiment_element_list = experiment_element.split()
    baseline_element_list = baseline_element.split()

    if len(experiment_element_list) == len(baseline_element_list):
        for nlp in experiment_element_list:
            for baseline in baseline_element_list:
                if nlp in baseline or baseline in nlp:
                    #This part is to check if the other words in the annotation is the same or not (ex. baseline:["quickly", "adds"] and nlp["slowly", "add"],
                    # when comparing "add" and "adds, it will also make sure that "quickly" and "slowly" are same for it to be pass, in this case, it is a fail)
                    nlp_remove_comparing_word = copy.deepcopy(experiment_element_list)
                    nlp_remove_comparing_word.remove(nlp)
                    baseline_remove_comparing_word = copy.deepcopy(baseline_element_list)
                    baseline_remove_comparing_word.remove(baseline)

                    if nlp_remove_comparing_word == baseline_remove_comparing_word:
                        return True
    return False

def relaxed_compare(baseline, experiment, pos_data, stanza_pos_nlp):
    '''
    calculate the number of true/false positives and false negatives for relaxed comparison mode

    Parameters:
    baseline (list): the elements being compared to 
    experiment (list): the elements comparing for accuracy 
    pos_data (2d list): contains the POS data for each annotation of the label type 
    stanza_pos_nlp (class): runs the stanza application to get the tags

    Returns:
    comparison_results (2D list): includes the elements identified as true/false positives and false negatives, including half points
    '''
    true_positive = []
    false_positive = []
    false_negative = []
    left_over_baseline = []
    left_over_nlp = []

    baseline_pos_tag, baseline_pos_text = pos_data

    for i in range(len(experiment)):
        nlp_element = experiment[i].lower().strip()
        not_true_positive = True

        #first checks if there are any exact cases
        for j in range (len(baseline)):
            baseline_element = baseline[j].lower().strip()
            if nlp_element == baseline_element:
                true_positive.append(baseline[j])
                baseline.pop(j)
                baseline_pos_tag.pop(j)
                baseline_pos_text.pop(j)
                not_true_positive = False
                break 

        if not_true_positive:
            left_over_nlp.append(nlp_element)

    left_over_baseline = copy.deepcopy(baseline)

    #Remove qualifiers from annotations
    baseline_text = []
    nlp_text = []
    remove_qualifiers = ["ADJ", "ADP", "ADV","AUX", "CCONJ", "DET", "INTJ", "PUNCT", "SCONJ", "X"]

    for i in range(len(baseline_pos_tag)):
        pos_text = ""

        for j in range(len(baseline_pos_tag[i])):
            if not(baseline_pos_tag[i][j] in remove_qualifiers):
                pos_text += baseline_pos_text[i][j] + " "
        baseline_text.append(pos_text)

    for i in range(len(left_over_nlp)):
        nlp_stanza = stanza_pos_nlp(left_over_nlp[i])
        pos_text = ""

        for sent in nlp_stanza.sentences:
            for word in sent.words:
                if not(word.upos in remove_qualifiers):
                    pos_text += word.text + " "
        nlp_text.append(pos_text)

    #Compare with removed Qualifiers
    for i in range(len(nlp_text)):
        nlp_element = nlp_text[i].lower().strip()
        not_true_positive = True

        #first checks if there are any exact cases
        for j in range (len(baseline_text)):
            baseline_element = baseline_text[j].lower().strip()

            if nlp_element == baseline_element:
                true_positive.append(left_over_baseline[j])
                left_over_baseline.pop(j)
                baseline_text.pop(j)
                not_true_positive = False
                break 

        #If it still not identified as true_positive, then the element is a false positive
        if not_true_positive:
            false_positive.append(left_over_nlp[i])

    false_negative = copy.deepcopy(left_over_baseline)
    comparison_results = [true_positive, false_positive, false_negative]

    return comparison_results

def count_true_false_positives_negatives(comparison_results):
    '''
    count the number of true/false positives and false negatives 

    Parameters:
    comparison_results (2D list): includes the elements identified as true/false positives and false negatives.

    Returns:
    number_comparison (2D list): the number of elements identified as true/false positives and false negatives
    '''
    true_positive, false_positive, false_negative = comparison_results
    number_true_positive = len(true_positive)
    number_false_positive = len(false_positive)
    number_false_negative = len(false_negative)

    number_comparison = [number_true_positive, number_false_positive, number_false_negative]

    return number_comparison

def count_total_result_dataset (total_comparison_results):
    '''
    counts the total number of true/false positives and false negatives 

    Parameters:
    number_comparison (2D list): the number of elements identified as true/false positives and false negatives

    Returns:
    total_count (list): total number of true/false positives and false negatives in dataset
    '''

    total_true_positive = 0
    total_false_positive = 0
    total_false_negative = 0

    for count in total_comparison_results:
        total_true_positive += count[0]
        total_false_positive += count[1]
        total_false_negative += count[2]

    total_count = [total_true_positive, total_false_positive, total_false_negative]

    return total_count

def total_dataset(count_list):
    '''
    Gets all the required info for the entire dataset

    Parameters:
    count_list (2D list): for each story, has the total count for true/false positives and false negative
    
    Returns:
    dataset_results (2D list): calculated precison, recall, and f-measure of persona, entity, action of the whole dataset
    '''

    count_persona_comparison_list, count_entity_comparison_list, count_action_comparison_list, count_benefit_comparison_list = count_list 

    total_persona_comparison = count_total_result_dataset(count_persona_comparison_list)
    total_entity_comparison = count_total_result_dataset(count_entity_comparison_list)
    total_action_comparison = count_total_result_dataset(count_action_comparison_list)
    total_benefit_comparison = count_total_result_dataset(count_benefit_comparison_list)

    dataset_persona_precision = calculate_precision(total_persona_comparison)
    dataset_entity_precision = calculate_precision(total_entity_comparison)
    dataset_action_precision = calculate_precision(total_action_comparison)
    dataset_benefit_precision = calculate_precision(total_benefit_comparison)

    dataset_persona_recall = calculate_recall(total_persona_comparison)
    dataset_entity_recall = calculate_recall(total_entity_comparison)
    dataset_action_recall = calculate_recall(total_action_comparison)
    dataset_benefit_recall = calculate_recall(total_benefit_comparison)

    total_persona_f_measure = calculate_f_measure(dataset_persona_precision, dataset_persona_recall)
    total_entity_f_measure = calculate_f_measure(dataset_entity_precision, dataset_entity_recall)
    total_action_f_measure = calculate_f_measure(dataset_action_precision, dataset_action_recall)
    total_benefit_f_measure = calculate_f_measure(dataset_benefit_precision, dataset_benefit_recall)

    
    dataset_precision = [dataset_persona_precision, dataset_entity_precision, dataset_action_precision, dataset_benefit_precision]
    dataset_recall = [dataset_persona_recall, dataset_entity_recall, dataset_action_recall, dataset_benefit_recall]
    dataset_f_measure = [total_persona_f_measure, total_entity_f_measure, total_action_f_measure, total_benefit_f_measure]
    
    dataset_results = [dataset_precision, dataset_recall, dataset_f_measure]

    return dataset_results

def calculate_precision(number_compared_results):
    '''
    calculate the precision

    Parameters:
    number_compared_results (list): total number of true/false positives and false negatives in dataset

    Returns:
    precision (float): the precision of the data
    '''
    if not number_compared_results:
        return None

    number_true_positive, number_false_positive, _ = number_compared_results

    if number_true_positive + number_false_positive == 0:
        precision = 0
    else:
        precision = number_true_positive / (number_true_positive + number_false_positive)

    return precision

def calculate_recall(number_compared_results):
    '''
    calculate the recall 

    Parameters:
    number_compared_results (list): total number of true/false positives and false negatives in dataset

    Returns:
    recall (float): the recall of the data
    '''
    if not number_compared_results:
        return None

    number_true_positive, _ , number_false_negative = number_compared_results

    if number_true_positive + number_false_negative == 0:
        recall = 0
    else:
        recall = number_true_positive / (number_true_positive + number_false_negative)

    return recall 

def calculate_f_measure (precision, recall):
    '''
    calculate the f measure 

    Parameters: 
    precision (float): the precision of the data
    recall (float): the recall of the data

    Returns:
    f_measure (float): the F-measure of the data
    '''
    if precision is None or recall is None:
        return None
    if (precision + recall) == 0:
        f_measure = 0
    else:
        f_measure = 2 * (precision * recall)/ (precision + recall)

    return f_measure

def individual_story(count_list):
    '''
    get all the precision, recall and f-measure results for each individual story

    Parameters:
    count_list (2D list): for each story, has the total count for true/false positives and false negative

    Returns:
    story_results (3D list): has the precision, recall and f-measure of each story for the persona, action, entity    
    '''
    count_persona_comparison_list, count_entity_comparison_list, count_action_comparison_list, count_benefit_comparison_list = count_list

    story_persona_precision = []
    story_entity_precision = []
    story_action_precision = []
    story_benefit_precision = []
    
    story_persona_recall = []
    story_entity_recall = []
    story_action_recall = []
    story_benefit_recall = []

    story_persona_f_measure = []
    story_entity_f_measure = []
    story_action_f_measure = []
    story_benefit_f_measure = []

    for i in range(len(count_persona_comparison_list)):
        persona_precision = calculate_precision(count_persona_comparison_list[i])
        entity_precision = calculate_precision(count_entity_comparison_list[i])
        action_precision = calculate_precision(count_action_comparison_list[i])

        story_persona_precision.append(persona_precision)
        story_entity_precision.append(entity_precision)
        story_action_precision.append(action_precision)

        persona_recall = calculate_recall(count_persona_comparison_list[i])
        entity_recall = calculate_recall(count_entity_comparison_list[i])
        action_recall = calculate_recall(count_action_comparison_list[i])

        story_persona_recall.append(persona_recall)
        story_entity_recall.append(entity_recall)
        story_action_recall.append(action_recall)

        persona_f_measure = calculate_f_measure(persona_precision, persona_recall)
        entity_f_measure = calculate_f_measure(entity_precision, entity_recall)
        action_f_measure = calculate_f_measure(action_precision, action_recall)

        story_persona_f_measure.append(persona_f_measure)
        story_entity_f_measure.append(entity_f_measure)
        story_action_f_measure.append(action_f_measure)

        if not count_benefit_comparison_list:
            story_benefit_precision = None
            story_benefit_recall = None
            story_benefit_f_measure = None

    precision_results = [story_persona_precision, story_entity_precision, story_action_precision, story_benefit_precision]
    recall_results = [story_persona_recall, story_entity_recall, story_action_recall, story_benefit_recall]
    f_measure_results = [story_persona_f_measure, story_entity_f_measure, story_action_f_measure, story_benefit_f_measure]

    story_results = [precision_results, recall_results, f_measure_results]

    return story_results

def output_results(count_list, save_folder_path, comparison_mode, backlog_name):
    ''''
    Ouput the results to various formats

    Parameters:
    count_list (3D list): has the count for persona, entity, action results for each story for the number of true/false postive and false negative
    save_folder_path (str): the path of the folder to save results
    csv_folder_path (str): path to save final results to 
    comparison_mode (int): the mode of the comparision that was completed on the data (1-strict, 2-inclusive, 3-relaxed)
    '''

    dataset_results = total_dataset(count_list)

    save_csv(save_folder_path, dataset_results, comparison_mode, backlog_name)

    return dataset_results
    

def bargraph(save_folder_path):
    '''
    runs the commands to graph the average precision, recall and f-measure of the total backlog and three comparison modes as a bargraph

    Parameters:
    story_results (3D list): contains the data of precision, recall and f-measure of each story
    x_axis_data (list): the interval for the data to be set up in 
    save_folder_path (str): path of the folder to save the graphs

    '''
    # read the csv files 
    with open(save_folder_path + "/strict_dataset_results.csv", 'r') as f:
        reader = csv.reader(f)
        strict_results = list(reader)

    with open(save_folder_path + "/inclusive_dataset_results.csv", 'r') as f:
        reader = csv.reader(f)
        inclusive_results = list(reader)

    with open(save_folder_path + "/relaxed_dataset_results.csv", 'r') as f:
        reader = csv.reader(f)
        relaxed_results = list(reader)

    
    strict_persona_f1 = setup_bargraph_data([float(row[10]) for row in strict_results[1:]])
    strict_entity_f1 = setup_bargraph_data([float(row[11]) for row in strict_results[1:]])
    strict_action_f1 = setup_bargraph_data([float(row[12]) for row in strict_results[1:]])

    inclusive_persona_f1 = setup_bargraph_data([float(row[10]) for row in inclusive_results[1:]])
    inclusive_entity_f1 = setup_bargraph_data([float(row[11]) for row in inclusive_results[1:]])
    inclusive_action_f1 = setup_bargraph_data([float(row[12]) for row in inclusive_results[1:]])

    relaxed_persona_f1 = setup_bargraph_data([float(row[10]) for row in relaxed_results[1:]])
    relaxed_entity_f1 = setup_bargraph_data([float(row[11]) for row in relaxed_results[1:]])
    relaxed_action_f1 = setup_bargraph_data([float(row[12]) for row in relaxed_results[1:]])

    create_bargraph(strict_persona_f1, strict_entity_f1, strict_action_f1, inclusive_persona_f1, inclusive_entity_f1, inclusive_action_f1, relaxed_persona_f1, relaxed_entity_f1, relaxed_action_f1, save_folder_path)
    
def setup_bargraph_data(story_data):
    '''
    sets up the data for the bar graph

    Parameters:
    story_data (list): contains the data to be set up 

    Returns:
    avg_data (float): the average data of the story data
    '''
    avg_data = statistics.mean(story_data)

    return avg_data

def create_bargraph(strict_persona_f1, strict_entity_f1, strict_action_f1, inclusive_persona_f1, inclusive_entity_f1, inclusive_action_f1, relaxed_persona_f1, relaxed_entity_f1, relaxed_action_f1, save_folder_path):
    '''
    creates and saves the bargraph

    Parameters
    strict_persona_f1, strict_entity_f1, strict_action_f1: F1 scores for strict mode
    inclusive_persona_f1, inclusive_entity_f1, inclusive_action_f1: F1 scores for inclusive mode
    relaxed_persona_f1, relaxed_entity_f1, relaxed_action_f1: F1 scores for relaxed mode
    save_folder_path (str): the path to save the graphs
    '''
    labels = ['Persona', 'Entity', 'Action']
    strict_data = [strict_persona_f1, strict_entity_f1, strict_action_f1]
    inclusive_data = [inclusive_persona_f1, inclusive_entity_f1, inclusive_action_f1]
    relaxed_data = [relaxed_persona_f1, relaxed_entity_f1, relaxed_action_f1]

    x = np.arange(len(labels))  # the label locations
    width = 0.2  # the width of the bars

    fig, ax = plt.subplots()
    rects1 = ax.bar(x - width, strict_data, width, label='Strict', color = plt.cm.Pastel1(0))
    rects2 = ax.bar(x, inclusive_data, width, label='Inclusive', color = plt.cm.Pastel1(1))
    rects3 = ax.bar(x + width, relaxed_data, width, label='Relaxed', color = plt.cm.Pastel1(2))

    # Add some text for labels, title and custom x-axis tick labels, etc.
    ax.set_ylabel('F1 Scores')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()

    fig.tight_layout()

    plt.savefig(os.path.join(save_folder_path, 'f1_bargraph.png'))

def save_csv(save_folder_path, dataset_results, comparison_mode, backlog_name):
    '''
    save the final results of dataset precision, recall and f-measure of persona, entity, action, and benefit to a csv file

    Parameters:
    saving_folder_path (str): path to the folder to save the data 
    dataset_results (2D list): calculated precison, recall, and f-measure of persona, entity, action, and benefit of the whole dataset
    comparison_mode (int): the mode of the comparision that was completed on the data (1-strict, 2-inclusive, 3-relaxed)
    '''
    dataset_precision, dataset_recall, dataset_f_measure = dataset_results

    persona_precision, entity_precision, action_precision, benefit_precision = dataset_precision 
    persona_recall, entity_recall, action_recall, benefit_recall = dataset_recall
    persona_f_measure, entity_f_measure, action_f_measure, benefit_f_measure = dataset_f_measure

    if comparison_mode == 1:
        saving_path = save_folder_path + "/strict_dataset_results.csv"
    elif comparison_mode == 2:
        saving_path = save_folder_path + "/inclusive_dataset_results.csv"
    else:
        saving_path = save_folder_path + "/relaxed_dataset_results.csv"

    data = [backlog_name,comparison_mode,persona_precision, entity_precision, action_precision, benefit_precision, persona_recall, entity_recall, action_recall, benefit_recall, persona_f_measure, entity_f_measure, action_f_measure, benefit_f_measure]

    # Initialize the rows with the header if the file does not exist
    if not os.path.exists(saving_path):
        rows = [["Backlog Name", "Comparison Mode", "Persona Precision", "Entity Precision", "Action Precision", "Benefit Precision", "Persona Recall", "Entity Recall", "Action Recall", "Benefit Recall", "Persona F-Measure", "Entity F-Measure", "Action F-Measure", "Benefit F-Measure"]]
    else:
        # Read the existing data
        with open(saving_path, "r") as file:
            reader = csv.reader(file)
            rows = list(reader)

    # Check if the backlog is already in the file and replace the row if it is
    for i, row in enumerate(rows):
        if row[0] == backlog_name:
            rows[i] = data
            break
    else:
        # If the backlog was not found in the file, append the new data
        rows.append(data)

    # Write the data back to the file
    with open(saving_path, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(rows)

    # returns the values found in the csv file
    persona_precision = [row[2] for row in rows[1:]]
    persona_recall = [row[6] for row in rows[1:]]
    persona_f_measure = [row[10] for row in rows[1:]]
    entity_precision = [row[3] for row in rows[1:]]
    entity_recall = [row[7] for row in rows[1:]]
    entity_f_measure = [row[11] for row in rows[1:]]
    action_precision = [row[4] for row in rows[1:]]
    action_recall = [row[8] for row in rows[1:]]
    action_f_measure = [row[12] for row in rows[1:]]
    benefit_precision = [row[5] for row in rows[1:]]
    benefit_recall = [row[9] for row in rows[1:]]
    benefit_f_measure = [row[13] for row in rows[1:]]

    # Pack the precision, recall, and F1 score for each category into separate lists
    story_precision_results = [persona_precision, entity_precision, action_precision, benefit_precision]
    story_recall_results = [persona_recall, entity_recall, action_recall, benefit_recall]
    story_f_measure_results = [persona_f_measure, entity_f_measure, action_f_measure, benefit_f_measure]

    # Return the lists
    return story_precision_results, story_recall_results, story_f_measure_results

def load_json(file):
    with open(file, 'r') as f:
        data = json.load(f)
    return data

def extract_all_baseline_info(path):
    '''
    Extracts the info from the baseline 

    Parameters:
    path (str): path to the file

    Returns:
    baseline_data (2D list): contains text, persona, entities, and actions identified by the baseline data
    pos_data (3D list): contains the text and the POS of the each annotation in each story 
    '''
    text = []
    persona = []
    entity = []
    action = []
    benefit = []

    persona_pos = []
    entity_pos = []
    action_pos = []


    file = open(path, encoding= "utf-8")
    data = json.load(file)

    for story in data:
        text.append(story["Text"])
        persona.append(story["Persona"])

        primary_entity = story["Entity"]["Primary Entity"]
        secondary_entity = story["Entity"]["Secondary Entity"]
        primary_action = story["Action"]["Primary Action"]
        secondary_action = story["Action"]["Secondary Action"]
        benefit.append([story["Benefit"]])

        persona_pos.append([story["Persona POS"]["Persona POS tag"], story["Persona POS"]["Persona POS text"]])

        primary_entity_pos = story["Entity POS"]["Primary Entity POS"]["Primary Entity POS tag"]
        secondary_entity_pos = story["Entity POS"]["Secondary Entity POS"]["Secondary Entity POS tag"]
        primary_action_pos = story["Action POS"]["Primary Action POS"]["Primary Action POS tag"]
        secondary_action_pos = story["Action POS"]["Secondary Action POS"]["Secondary Action POS tag"]

        story_action = primary_action + secondary_action
        story_entity = primary_entity + secondary_entity

        while "" in story_action:
            story_action.remove("")

        action.append(story_action)

        while "" in story_entity:
            story_entity.remove("")
        
        entity.append(story_entity)

        if primary_action_pos !=[[]] and secondary_action_pos != [[]]:
            action_pos.append([primary_action_pos + secondary_action_pos, story["Action POS"]["Primary Action POS"]["Primary Action POS text"] + story["Action POS"]["Secondary Action POS"]["Secondary Action POS text"]])
        elif primary_action_pos != [[]]:
            action_pos.append([primary_action_pos, story["Action POS"]["Primary Action POS"]["Primary Action POS text"]])
        else:
            action_pos.append([secondary_action_pos, story["Action POS"]["Secondary Action POS"]["Secondary Action POS text"]])

        if primary_entity_pos != [[]] and secondary_entity_pos != [[]]:
            entity_pos.append([primary_entity_pos + secondary_entity_pos, story["Entity POS"]["Primary Entity POS"]["Primary Entity POS text"] + story["Entity POS"]["Secondary Entity POS"]["Secondary Entity POS text"]])
        elif primary_entity_pos != [[]]:
            entity_pos.append([primary_entity_pos, story["Entity POS"]["Primary Entity POS"]["Primary Entity POS text"]])
        else:
            entity_pos.append([secondary_entity_pos, story["Entity POS"]["Secondary Entity POS"]["Secondary Entity POS text"]])

    file.close()

    baseline_data = [text, persona, entity, action, benefit]
    pos_data = [persona_pos, entity_pos, action_pos]

    return baseline_data, pos_data

def extract_experiment_info(path):
    '''
    Extracts the info from experiment resutls 

    Parameters:
    path (str): path to the file

    Returns:
    experiment_data (2D list): contains text, persona, primary entities, primary actions, and benefit identified by the experiment
    '''
    text = []
    persona = []
    entity = []
    action = []
    benefit = []

    file = open(path, mode= "r", encoding= "utf-8")
    with open(path, 'r') as f:
        data = json.load(f)
    

    for story in data:
        text.append(story["Text"])
        persona.append(story["Persona"])

        primary_entity = story["Entity"]["Primary Entity"]
        secondary_entity = story["Entity"]["Secondary Entity"]
        primary_action = story["Action"]["Primary Action"]
        secondary_action = story["Action"]["Secondary Action"]
        benefit.append([story["Benefit"]])

        story_action = primary_action + secondary_action
        story_entity = primary_entity + secondary_entity

        while "" in story_action:
            story_action.remove("")

        action.append(story_action)

        while "" in story_entity:
            story_entity.remove("")
        
        entity.append(story_entity)
        
    file.close()

    experiment_data = [text, persona, entity, action, benefit]

    return experiment_data

def check_valid_comparison(comparison):
    '''
    check if the comparison is valid

    Parameters:
    comparison (int): the mode of the comparision that was completed on the data (1-strict, 2-inclusive, 3-relaxed)

    Returns:
    True if the comparison is valid
    False if the comparison is not valid
    '''
    if comparison not in [1,2,3,4]:
        return "Comparison mode is not valid (1-strict, 2-inclusive, 3-relaxed, 4-bert_score)"
    return True

def map_backlog(experiment_results_folder_path):
    '''
    map the backlog name to the ground truth and experiment file paths

    Parameters:
    experiment_results_folder_path (str): the path to the folder containing the results of the experiment

    Returns:
    backlog_map (dict): the dictionary mapping the backlog name to the ground truth and experiment file paths
    '''
    keys = ["g02", "g03", "g04", "g05", "g08", "g10", "g11", "g12", "g13", "g14", "g16", "g17", "g18", "g19", "g21", "g22", "g23", "g24", "g25", "g26", "g27", "g28"]
    backlog_map = {}
    missing_backlogs = set(keys)

    ## check ground truth files
    for file in os.listdir('pos_baseline'):
        for key in keys:
            if key in file:
                backlog_map[key] = [file]
        

    ## check experiment files
    for file in os.listdir(experiment_results_folder_path):
        for key in keys:
            if key in file:
                backlog_map[key].append(file)
                missing_backlogs.discard(key)  # remove key from missing_backlogs

    print(f"Missing backlogs: {sorted(list(missing_backlogs))}")
    return backlog_map

def calculate_bert_score(reference_list, candidate_list):
    """
    Calculate the BERTScore based on the reference (pos_baseline) and candidate lists (experiment data).

    Parameters:
    reference_list (list): ground truth
    candidate_list (list): experiment data

    Returns:
    precision (float): the precision of the experiment data
    recall (float): the recall of the experiment data
    f1 (float): the F-measure of the experiment data
    """

    if reference_list==[""] and candidate_list==[""]:
        return 1.0, 1.0, 1.0

    matched_references = set()  # Keep track of matched references
    P_list, R_list, F1_list = [], [], []
    
    for candidate in candidate_list:
        best_F1 = 0
        best_ref = None
        
        for i, reference in enumerate(reference_list):
            if i not in matched_references:  # Only match unused references
                P, R, F1 = score([candidate], [reference], lang="en", verbose=False)
                if F1.mean().item() > best_F1:
                    best_F1 = F1.mean().item()
                    best_ref = i
        
        if best_ref is not None:
            matched_references.add(best_ref)
        
        F1_list.append(best_F1)
    
    # Precision: How many candidate items matched references
    precision = len(matched_references) / len(candidate_list) if candidate_list else 0
    
    # Recall: How many reference items were captured
    recall = len(matched_references) / len(reference_list) if reference_list else 0
    
    # F1 Score
    f1 = 2 * (precision * recall) / (precision + recall) if precision + recall > 0 else 0

    return precision, recall, f1

def bert_score(baseline_data, experiment_data):
    """
    
    """
    sorted_baseline_data, sorted_experiment_data, sorted_pos, missing_stories = sort(baseline_data, experiment_data, pos_data=None)
    baseline_text, baseline_persona, baseline_entity, baseline_action, baseline_benefit = sorted_baseline_data
    _, experiment_persona, experiment_entity, experiment_action, experiment_benefit = sorted_experiment_data

    f1_persona_list = []
    f1_entity_list = []
    f1_action_list = []
    f1_benefit_list = []
    
    for i in range(len(baseline_text)):

        P, R, F1_persona = calculate_bert_score(baseline_persona[i], experiment_persona[i])
        P, R, F1_entity = calculate_bert_score(baseline_entity[i], experiment_entity[i])
        P, R, F1_action = calculate_bert_score(baseline_action[i], experiment_action[i])
        P, R, F1_benefit = calculate_bert_score(baseline_benefit[i], experiment_benefit[i])

        f1_persona_list.append(F1_persona)
        f1_entity_list.append(F1_entity)
        f1_action_list.append(F1_action)
        f1_benefit_list.append(F1_benefit)

    # calculate the average F1 score for each category
    f1_persona = sum(f1_persona_list) / len(f1_persona_list)
    f1_entity = sum(f1_entity_list) / len(f1_entity_list)
    f1_action = sum(f1_action_list) / len(f1_action_list)
    f1_benefit = sum(f1_benefit_list) / len(f1_benefit_list)

    print(f"F1 Persona: {f1_persona}, F1 Entity: {f1_entity}, F1 Action: {f1_action}, F1 Benefit: {f1_benefit}")

    return f1_persona, f1_entity, f1_action, f1_benefit
    
    
def save_bert(save_folder_path, f1_persona, f1_entity, f1_action, f1_benefit, backlog_name):

    saving_path = save_folder_path + "/bert_dataset_results.csv"

    data = [backlog_name, "4" ,f1_persona, f1_entity, f1_action, f1_benefit]

    # Initialize the rows with the header if the file does not exist
    if not os.path.exists(saving_path):
        rows = [["Backlog Name", "Comparison Mode", "Persona Bert_score F-Measure", "Entity Bert_score F-Measure", "Action Bert_score F-Measure", "Benefit Bert_score F-Measure"]]
    else:
        # Read the existing data
        with open(saving_path, "r") as file:
            reader = csv.reader(file)
            rows = list(reader)

    # Check if the backlog is already in the file and replace the row if it is
    for i, row in enumerate(rows):
        if row[0] == backlog_name:
            rows[i] = data
            break
    else:
        # If the backlog was not found in the file, append the new data
        rows.append(data)

    # Write the data back to the file
    with open(saving_path, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(rows)

    return None




if __name__ == "__main__":
    '''
    This scripts performs an evaluation of an extraction tool against the baseline (ground truth) data.

    Parameters:
    experiment_results_folder_path (str): the path to the folder containing the results of the experiment, the files there should contain the backlog_name.
    experiment_name (str): the name of the experiment, it will be used to identify the files in the save_path
    comparison (int): the mode of the comparision that was completed on the data (1-strict, 2-inclusive, 3-relaxed, 4-bert_score)

    '''
    ## DEFINE VARIABLES
    #stanza.download('en') 
    experiment_results_folder_path = "extracted-user-stories/ollama3"
    experiment_name = "ollama3"
    
    # Define comparison modes
    comparison = [1,2,3,4]

    ## SAVING PATH
    save_path = "evaluation/"+experiment_name

    ## Checks if variables are valid 
    if not os.path.isdir(experiment_results_folder_path):
        print(f"Folder does not exist: {experiment_results_folder_path}")
        sys.exit()

    if experiment_name == "":
        print("Experiment name is empty")
        sys.exit()

    if not os.path.isdir(save_path):
        try: 
            os.makedirs(save_path)
        except OSError:
            print(f"Creation of the directory {save_path} failed")
            sys.exit()

    if comparison < 1 or comparison > 4:
        print("Comparison mode is not valid (1-strict, 2-inclusive, 3-relaxed, 4-bert_score)")
        sys.exit()

    ## Create dictionary to map the backlog name to ground truth and experiment file paths
    backlog_map = map_backlog(experiment_results_folder_path)

    for backlog_name, values in backlog_map.items():
        print(f"Backlog: {backlog_name}")
        if len(values) == 2:
            baseline_file_name, experiment_results_file_name = values
            baseline_file_path = os.path.join("pos_baseline", baseline_file_name)
            experiment_results_file_path = os.path.join(experiment_results_folder_path, experiment_results_file_name)
            
            stanza_pos_nlp = None
            
            ## Run the comparison
            for mode in comparison:
                ## Extract the data from the files
                baseline_data, pos_data = extract_all_baseline_info(baseline_file_path)
                experiment_data = extract_experiment_info(experiment_results_file_path)
                
                if mode == 3:
                    stanza_pos_nlp = stanza.Pipeline('en')

                if mode in range(1,4):
                    all_story_results, all_count_list, all_comparison_collection, all_missing_stories, all_baseline_text = compare_and_get_results(baseline_data, experiment_data, mode, pos_data, stanza_pos_nlp)
                    output_results(all_count_list, save_path, mode, backlog_name)

                if mode == 4:
                    f1_persona, f1_entity, f1_action, f1_benefit =  bert_score(baseline_data, experiment_data)
                    save_bert(save_path, f1_persona, f1_entity, f1_action, f1_benefit, backlog_name)

    bargraph(save_path)
