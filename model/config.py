'''
MODEL CONFIGURATION
'''

class CONFIGURATION(object):
    def __init__(self, feat_type='fc7'):
        
        self.feat_type = feat_type
        self.ACTION_NUM = 117
        # graph head model
        self.G_H_L_S = [12544, 2048, 2048]   # 
        self.G_H_A   = ['ReLU', 'ReLU']
        self.G_H_B   = True
        self.G_H_BN  = False
        self.G_H_D   = 0.2

        if feat_type=='fc7':
            # # gnn node function
            self.G_N_L_S = [1024*2, 1024]
            self.G_N_A   = ['ReLU']
            self.G_N_B   = True
            self.G_N_BN  = False
            self.G_N_D   = False
            self.G_N_GRU = 1024

            # gnn edge function
            self.G_E_L_S = [1024*2, 1024]
            self.G_E_A   = ['ReLU']
            self.G_E_B   = True
            self.G_E_BN  = False
            self.G_E_D   = False

            # gnn attention mechanism
            self.G_A_L_S = [1024, 1]
            self.G_A_A   = ['LeakyReLU']
            self.G_A_B   = False
            self.G_A_BN  = False
            self.G_A_D   = False
        else:
            # gnn node function
            self.G_N_L_S = [2048*2, 1024]
            self.G_N_A   = ['ReLU']
            self.G_N_B   = True
            self.G_N_BN  = False
            self.G_N_D   = False
            self.G_N_GRU = 1024

            # gnn edge function
            self.G_E_L_S = [2048*2, 1024]
            self.G_E_A   = ['ReLU']
            self.G_E_B   = True
            self.G_E_BN  = False
            self.G_E_D   = False

            # gnn attention mechanism
            self.G_A_L_S = [1024, 1]
            self.G_A_A   = ['LeakyReLU']
            self.G_A_B   = False
            self.G_A_BN  = False
            self.G_A_D   = False

    #@staticmethod
    def save_config(self):
        model_config = {'graph_head':{}, 
                        'graph_node':{},
                        'graph_edge':{},
                        'graph_attn':{}}
        CONFIG=self.__dict__
        for k, v in CONFIG.items():
            if 'G_H' in k:
                model_config['graph_head'][k]=v
            elif 'G_N' in k:
                model_config['graph_node'][k]=v
            elif 'G_E' in k:
                model_config['graph_edge'][k]=v
            elif 'G_A' in k:
                model_config['graph_attn'][k]=v
            else:
                model_config[k]=v
        
        return model_config

if __name__=="__main__":
    data_const = CONFIGURATION()
    data_const.save_config()
