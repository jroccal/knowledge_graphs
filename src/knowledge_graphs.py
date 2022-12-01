import numpy as np
import pandas as pd
from collections import Counter

import re
import nltk
import string
import codecs
import unicodedata
from unidecode import unidecode
from nltk.corpus import stopwords


import transformers
from tqdm import tqdm
from transformers import pipeline

import spacy
from spacy import displacy

from pyvis.network import Network

import matplotlib.pyplot as plt

## download stopwords
nltk.download('stopwords')
nlp = spacy.load("en_core_web_sm")


stop_words = stopwords.words('english')
non_characters = """'!"#$%&()*+,¿¡/:;<=>?@[\\]^_-`{|}~"""
def preprocess_text_ps(text, stopwords=[]):
    token_list = []
    for token in text.split(' '):
        lowered_token = token.lower()        
        lowered_token = unidecode(lowered_token)
        if re.search(r'.[a-z].', lowered_token):
            lowered_token = lowered_token.replace('.', ' . ')
        #if re.match(r',[a-z],', lowered_token):
        #    lowered_token = lowered_token.replace(',', ' , ')
        if re.search(r'\\...\\...\\[a-z][0-9]{1,3}[a-z]', lowered_token):
          lowered_token = (re.sub(r"\\...\\...\\[a-z][0-9]{1,3}[a-z]", "", lowered_token))
        if re.search(r'\\...\\[a-z]{1,3}[0-9]{1,3}', lowered_token):  
          lowered_token = (re.sub(r"\\...\\[a-z]{1,3}[0-9]{1,3}", "", lowered_token))

        lowered_token = lowered_token.replace('-', ' ')
        translator = str.maketrans('', '', non_characters)
        lowered_token = lowered_token.translate(translator)
        #lowered_token = re.sub(r"\d+", "#", lowered_token)
        if (lowered_token is not '' or lowered_token is not ' ' or lowered_token is None) and lowered_token not in stopwords:
            token_list.append(lowered_token)

    return ' '.join(token_list)

def  clean_date(x):
  if str(x)[-4:].isnumeric():
    return int(str(x)[-4:])
  else:
    return 3000


class Knowledge_graph:
    def __init__(self, df_date_text, zero_shot_model):
        self.df_date_text = df_date_text 
        self.zero_shot_model = zero_shot_model
        
    def filter_nodes(self, nodes_raw, max_n_nodes = 10, min_n_nodes = 5, importance = 0.5):    
        nodes_clean = {}
        for key in nodes_raw.keys():
            count = Counter(nodes_raw[key])
            array_most_common = np.array(count.most_common())
            weight_words = np.int_(array_most_common[:,1])
            filter_ = np.cumsum(weight_words)/weight_words.shape[0] <= importance
            if np.sum(filter_) > max_n_nodes:
                nodes_clean[key] = array_most_common[0:max_n_nodes]
            elif np.sum(filter_) < min_n_nodes:
                nodes_clean[key] = array_most_common[0:min_n_nodes]
            else:
                nodes_clean[key] = array_most_common[filter_]

        return nodes_clean


    def obtain_keywords_from_ps(self, series_text):

        nodes_raw = {'actors':{},
                     'actions':{},                
                     'objects':{}
                     }

        for text_norm in tqdm(series_text):      
            doc_tmp = nlp(text_norm)
            for token in doc_tmp:        
                if token.pos_ == 'PROPN' and token.dep_ == 'nsubj':
                    if token.lemma_ in nodes_raw['actors']:
                        nodes_raw['actors'][token.lemma_] +=1
                    else: 
                        nodes_raw['actors'][token.lemma_] = 1

                elif token.pos_ == 'VERB' and token.dep_ == 'ROOT':
                    if token.lemma_ in nodes_raw['actions']:
                        nodes_raw['actions'][token.lemma_] +=1
                    else: 
                        nodes_raw['actions'][token.lemma_] = 1
        
                elif token.pos_ == 'NOUN' and token.dep_ == 'dobj':
                    if token.lemma_ in nodes_raw['objects']:
                        nodes_raw['objects'][token.lemma_] +=1
                    else: 
                        nodes_raw['objects'][token.lemma_] = 1

        return nodes_raw


    def predict_nodes(self, text, nodes_clean, importance=0.6, sample_sentences=None):    
        list_graphs = []
        if sample_sentences == None:
            sample_sentences = len(text.split('.'))
        for sentence in text.split('.')[0:sample_sentences]: 
            sentence = sentence.strip()      

            if len(sentence.split()) >= 3:
                graph_tmp = {}
                for class_ in nodes_clean.keys():        
                    prediction = self.zero_shot_model(sentence, list(nodes_clean[class_][:,0]))    
                    filter_ = np.cumsum(prediction['scores']) <=importance
                    if np.sum(filter_)>0:
                        graph_tmp[class_] = list(np.array(prediction['labels'])[filter_])
                    else:
                        graph_tmp[class_] = prediction['labels'][0:1]
    
                list_graphs.append(graph_tmp)
    
        return list_graphs


    def compute_edges(self, list_graphs):
        list_src_dst = []
        for dict_tmp in list_graphs:
            list_src_dst.append({'src':dict_tmp['actors'][0], 'dst':dict_tmp['actions'][0]})
            list_src_dst.append({'src':dict_tmp['actions'][0], 'dst':dict_tmp['objects'][0]})

        df_graph = pd.DataFrame(list_src_dst)
        df_graph_edges = df_graph.reset_index().groupby(['src', 'dst']).count()
        return df_graph_edges

    def build_grap(self, list_years=[2016, 2017, 2018, 2019, 2020, 2021, 2022], 
                   max_n_nodes = 10, min_n_nodes = 5, importance_nodes = 0.5, importance_prediction=0.6,
                   sample_texts = None, sample_sentences=None, batch_size=10):
    
        list_graphs_year = []
        for year in list_years:
            if year == 2016:        
                series_text = self.df_date_text[self.df_date_text['date']<=year]['text_norm']
                series_text_graph = self.df_date_text[self.df_date_text['date']<=year]['text_norm_graph']
            elif year == 2022:
                series_text = self.df_date_text[self.df_date_text['date']>=year]['text_norm']
                series_text_graph = self.df_date_text[self.df_date_text['date']>=year]['text_norm_graph']
            else:      
                series_text = self.df_date_text[self.df_date_text['date']==year]['text_norm']
                series_text_graph = self.df_date_text[self.df_date_text['date']==year]['text_norm_graph']

            display(series_text)
            """
            print('\ncomputing nodes to ', year)  
            self.nodes_raw = self.obtain_keywords_from_ps(self.series_text.iloc[2:3])
            print('raw nodes')
            # print(len(nodes['actions']), len(nodes['actors']), len(nodes['objects']))      

            self.nodes = self.filter_nodes(self.nodes_raw, max_n_nodes = max_n_nodes, min_n_nodes = min_n_nodes, importance = importance_nodes)
            print('clean nodes')
            print(self.nodes['actions'].shape, self.nodes['actors'].shape, self.nodes['objects'].shape)
            """
      
            print('\ncomputing graph to ', year)    
            if sample_texts == None:
                sample_texts = series_text_graph.shape[0]  

            index_texts = list(series_text_graph.sample(sample_texts).index)         

            for index in tqdm(index_texts):

                print('\ncomputing nodes to ', year)  
                nodes = self.obtain_keywords_from_ps([series_text.loc[index]])      
                nodes = self.filter_nodes(nodes, max_n_nodes = max_n_nodes, min_n_nodes = min_n_nodes, importance = importance_nodes)
                print('clean nodes')
                print(nodes['actions'].shape, nodes['actors'].shape, nodes['objects'].shape)
                print(nodes['actors'].T)
                print(nodes['actions'].T)
                print(nodes['objects'].T)
                print(series_text_graph.loc[index])

                list_graph = self.predict_nodes(series_text_graph.loc[index], nodes, importance=importance_prediction, 
                                                sample_sentences=sample_sentences)
                df_graph = self.compute_edges(list_graph)
                list_graphs_year.append(df_graph)
                print('for text with ',len(series_text_graph.loc[index].split('.')),' sentences')
                display(self.df_graph)

        return list_graphs_year

