# neg_sharing (no additional neg sampling)
import random
import numpy as np
import time
from utilities import get_cur_time, nan_detection
from train_base import TrainerBase

class Trainer(TrainerBase):
    def __init__(self, model_dict, conf, data_helper):
        super(Trainer, self).__init__(model_dict, conf, data_helper)
        self.model_train = model_dict['model']
        self.model_all_loss = model_dict['model_all_loss']
        self.neg_sign = np.array([-1], dtype='int32') \
            if conf.loss == 'skip-gram' else 0
        self.sample_batch = data_helper.sampler_dict['sample_batch']
        try:
            self.monitor_rate = conf.monitor_rate_all_loss
        except:
            self.monitor_rate = 0  # set this > 0 if want to monitor other losses

    def train(self, eval_scheme=None, use_async_eval=True):
        model_train = self.model_train
        model_all_loss = self.model_all_loss
        neg_sign = self.neg_sign
        conf = self.conf
        num_negatives = conf.num_negatives
        batch_size_p = conf.batch_size_p
        data_helper = self.data_helper
        sample_batch = self.sample_batch
        train = data_helper.data['train']
        C = data_helper.data['C']

        train_time = []
        for epoch in range(conf.max_epoch + 1):
            bb, b = 0, batch_size_p
            np.random.shuffle(train)
            cost, it = 0, 0
            monitor_losses = model_all_loss.keys()
            costs = dict(zip(monitor_losses, np.zeros(len(monitor_losses))))
            monitor_rate, monitor_it = self.monitor_rate, 0

            t_start = time.time()
            while epoch > 0 and bb < len(train):
                it += 1
                b = bb + batch_size_p
                if b > len(train):
                    # get rid of uneven tail so no need to dynamically adjust batch_size_p
                    break
                train_batch_p = train[bb: b]
                train_batch_n = train_batch_p.repeat(num_negatives, axis=0)
                train_batch_n[:, 1] = sample_batch(num_negatives * batch_size_p)
                train_batch_n[:, 2] = neg_sign
                train_batch = np.vstack((train_batch_p, train_batch_n))
                user_batch = train_batch[:, 0]
                item_batch = train_batch[:, 1]
                response_batch = train_batch[:, 2]
                cost += model_train.train_on_batch([user_batch, item_batch],
                                                   [response_batch])
                if random.random() < monitor_rate:
                    monitor_it += 1
                    for lname, m in model_all_loss.iteritems():
                        neg_sign_tmp = np.array([-1], dtype='int32') \
                            if lname == 'skip-gram' else 0
                        response_batch[batch_size_p:] = neg_sign_tmp
                        costs[lname] += m.train_on_batch([user_batch,
                                                          item_batch],
                                                         [response_batch])
                bb = b
            if epoch > 0:
                train_time.append(time.time() - t_start)
            print get_cur_time(), 'epoch %d (%d it)' % (epoch, it), \
                'cost %.5f' % (cost / it if it > 0 else -1),
            nan_detection('cost', cost)
            if monitor_rate > 0:
                print '(',
                for loss in monitor_losses:
                    print '{}={}'.format(loss, costs[loss] / monitor_it 
                                         if monitor_it > 0 else -1),
                print ')',
            if eval_scheme is None:
                print ''
            else:
                async_eval = True \
                    if use_async_eval and epoch != conf.max_epoch else False
                try: ps[-1].join()
                except: pass
                ps = self.test(eval_scheme, use_async_eval=async_eval)
        print 'Training time (sec) per epoch:', np.mean(train_time)
